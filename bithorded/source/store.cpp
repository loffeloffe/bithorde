/*
    Copyright 2012 Ulrik Mikaelsson <ulrik.mikaelsson@gmail.com>

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
*/

#include "store.hpp"

#include <boost/algorithm/string/predicate.hpp>
#include <boost/filesystem.hpp>
#include <boost/make_shared.hpp>
#include <string>

#include <log4cplus/logger.h>
#include <log4cplus/loggingmacros.h>

using namespace std;

namespace asio = boost::asio;
namespace fs = boost::filesystem;

using namespace bithorded;
using namespace bithorded::source;

const int THREADPOOL_CONCURRENCY = 4;
const fs::path META_DIR = ".bh_meta";

namespace bithorded {
	log4cplus::Logger sourceLog = log4cplus::Logger::getInstance("source");
}

Store::Store(boost::asio::io_service& ioSvc, const boost::filesystem3::path& baseDir) :
	_threadPool(THREADPOOL_CONCURRENCY),
	_ioSvc(ioSvc),
	_baseDir(baseDir),
	_store(baseDir/META_DIR)
{
	if (!fs::exists(_baseDir))
		throw ios_base::failure("LinkedAssetStore: baseDir does not exist");
	_store.open();
}

struct HashTask : public Task {
	SourceAsset::Ptr asset;
	asio::io_service& io_svc;
	asio::io_service::work _work;

	HashTask(SourceAsset::Ptr asset, asio::io_service& io_svc)
		: asset(asset), io_svc(io_svc), _work(io_svc)
	{}

	void operator()() {
		asset->notifyValidRange(0, asset->size());

		io_svc.post(boost::bind(&SourceAsset::updateStatus, asset));
		delete this;
	}
};

bool path_is_in(const fs::path& path, const fs::path& folder) {
	string path_(fs::absolute(path).string());
	string folder_(fs::absolute(folder).string()+'/');
	return boost::starts_with(path_, folder_);
}

IAsset::Ptr Store::addAsset(const boost::filesystem3::path& file)
{
	if (!path_is_in(file, _baseDir)) {
		return ASSET_NONE;
	} else {
		fs::path assetFolder(_store.newAssetDir());

		fs::create_directory(assetFolder);
		fs::create_symlink(file, assetFolder/"data");

		SourceAsset::Ptr asset = boost::make_shared<SourceAsset>(assetFolder);
		asset->statusChange.connect(boost::bind(&Store::_addAsset, this, asset.get()));
		HashTask* task = new HashTask(asset, _ioSvc);
		_threadPool.post(*task);
		return asset;
	}
}

void Store::_addAsset(SourceAsset* asset)
{
	BitHordeIds ids;
	if (asset && asset->getIds(ids)) {
		const char *data_path = (asset->folder()/"data").c_str();
		lutimes(data_path, NULL);

		_store.link(ids, asset->folder());
	}
}


std::string findTigerId(const BitHordeIds& ids) {
	for (auto iter=ids.begin(); iter != ids.end(); iter++) {
		if (iter->type() == bithorde::HashType::TREE_TIGER)
			return iter->id();
	}
	return "";
}

IAsset::Ptr Store::findAsset(const BitHordeIds& ids)
{
	std::string tigerId = findTigerId(ids);

	if (_tigerMap.count(tigerId)) {
		if (auto asset = _tigerMap[tigerId].lock())
			return asset;
		else
			_tigerMap.erase(tigerId);
	}

	auto path = _store.resolveIds(ids);
	if (!path.empty()) {
		auto asset = boost::make_shared<SourceAsset>(path);
		if (asset->hasRootHash()) {
			if (tigerId.size())
				_tigerMap[tigerId] = asset;
			return asset;
		} else {
			LOG4CPLUS_WARN(sourceLog, "Unhashed asset detected, hashing");
			_threadPool.post(*new HashTask(asset, _ioSvc));
		}
	}
	return IAsset::Ptr();
}
