/*
    Copyright 2012 <copyright holder> <email>

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


/// TreeStore as described briefly in http://www.lucidchart.com/publicSegments/view/4f5910e5-22dc-4b22-ba2c-6fee0a7c6148

#ifndef TREESTORE_H
#define TREESTORE_H

#include <math.h>
#include <stdint.h>
#include <ostream>

#include <boost/assert.hpp>

inline uint parentlayersize(uint nodes) {
	if (nodes > 1)
		return (nodes+1)/2;
	else
		return 0;
}

inline uint treesize(uint leafs) {
	if (leafs > 1)
		return leafs + treesize(parentlayersize(leafs));
	else
		return leafs;
}

uint bottomlayersize(uint treesize, int layers=-1);

struct NodeIdx {
	uint nodeIdx;
	uint layerSize;

	NodeIdx(uint nodeIdx, uint layerSize) 
		: nodeIdx(nodeIdx), layerSize(layerSize)
	{}

	NodeIdx parent() {
		BOOST_ASSERT( not isRoot() );
		return NodeIdx(nodeIdx/2, parentlayersize(layerSize));
	}

	NodeIdx sibling() {
		return NodeIdx(nodeIdx ^ 0x01, layerSize);
	}

	bool isValid() {
		return nodeIdx < layerSize;
	}

	bool operator==(const NodeIdx& other) const {
		return (this->nodeIdx == other.nodeIdx)
			&& (this->layerSize == other.layerSize);
	}

	bool isRoot() {
		return (layerSize == 1);
	}
};

std::ostream& operator<<(std::ostream& str,const NodeIdx& idx);

template <typename Node, typename BackingStore> 
class TreeStore
{
public:
	TreeStore(BackingStore& backingStore, uint leafs) 
		: _storage(backingStore), _leafs(leafs)
	{
		BOOST_ASSERT(backingStore.size() >= treesize(leafs));
	}

	NodeIdx leaf(uint i) {
		return NodeIdx(i, _leafs);
	};
	
	Node& operator[](NodeIdx& idx) {
		int layer_offset = treesize(parentlayersize(idx.layerSize));
		return _storage[layer_offset + idx.nodeIdx];
	}

private:
	BackingStore& _storage;
	uint _leafs;
};

#endif // TREESTORE_H
