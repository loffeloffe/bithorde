#include <vector>

#include <boost/test/unit_test.hpp>

#include "bithorded/lib/treestore.hpp"

using namespace std;

#include "test_storage.hpp"

BOOST_AUTO_TEST_CASE( function_test )
{
	BOOST_CHECK_EQUAL( parentlayersize(0), 0 );
	BOOST_CHECK_EQUAL( parentlayersize(1), 0 );
	BOOST_CHECK_EQUAL( parentlayersize(2), 1 );
	BOOST_CHECK_EQUAL( parentlayersize(7), 4 );
	BOOST_CHECK_EQUAL( parentlayersize(8), 4 );
	BOOST_CHECK_EQUAL( parentlayersize(9), 5 );

	BOOST_CHECK_EQUAL( treesize(6), 6+3+2+1);
	BOOST_CHECK_EQUAL( treesize(7), 7+4+2+1);
	BOOST_CHECK_EQUAL( treesize(8), 8+4+2+1);
	BOOST_CHECK_EQUAL( treesize(9), 9+5+3+2+1);

	for (int i=1; i < 64; i++) {
		auto ts = treesize(i);
		auto leaves = calcLeaves(ts);
		BOOST_CHECK_EQUAL( leaves, i );
	}
}

BOOST_AUTO_TEST_CASE( idx_test )
{
	TestStorage<int> store(treesize(6));
	for (uint i=0; i < store.size(); i++)
		*store[i] = i;

	TreeStore<int, TestStorage<int>> tree(store);
	NodeIdx idx(0,1);

	BOOST_CHECK( NodeIdx(0,1).isValid() );
	BOOST_CHECK( not NodeIdx(0,0).isValid() );
	BOOST_CHECK( not NodeIdx(1,0).isValid() );

	BOOST_CHECK_EQUAL( tree.leaf(0), NodeIdx(0,6) );
	BOOST_CHECK_EQUAL( tree.leaf(5), NodeIdx(5,6) );

	idx = tree.leaf(0); BOOST_CHECK_EQUAL( *tree[idx], 6 );
	idx = tree.leaf(5); BOOST_CHECK_EQUAL( *tree[idx], 11 );

	BOOST_CHECK_EQUAL( NodeIdx(0,2).parent(), NodeIdx(0,1) );
	BOOST_CHECK_EQUAL( NodeIdx(1,2).parent(), NodeIdx(0,1) );
	BOOST_CHECK_EQUAL( NodeIdx(0,6).parent(), NodeIdx(0,3) );
	BOOST_CHECK_EQUAL( NodeIdx(2,6).parent(), NodeIdx(1,3) );
	BOOST_CHECK_EQUAL( NodeIdx(4,6).parent(), NodeIdx(2,3) );
	BOOST_CHECK_EQUAL( NodeIdx(5,6).parent(), NodeIdx(2,3) );

	BOOST_CHECK( tree.leaf(5).parent().parent().parent().isRoot() );
	BOOST_CHECK( not tree.leaf(5).parent().parent().isRoot() );

	BOOST_CHECK_EQUAL( NodeIdx(0,2).sibling(), NodeIdx(1,2) );
	BOOST_CHECK_EQUAL( NodeIdx(1,2).sibling(), NodeIdx(0,2) );
	BOOST_CHECK_EQUAL( NodeIdx(0,5).sibling(), NodeIdx(1,5) );
	BOOST_CHECK_EQUAL( NodeIdx(1,5).sibling(), NodeIdx(0,5) );
	BOOST_CHECK( not NodeIdx(4,5).sibling().isValid() );
}
