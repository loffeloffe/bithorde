/****************************************************************************************
 * Copyright: Ulrik Mikaelsson, All rights reserved
 ***************************************************************************************/
module daemon.routing.router;

private import tango.time.Time;

private import lib.message;

private import daemon.client;
private import daemon.routing.asset;
private import daemon.routing.friend;
private import daemon.server;

/****************************************************************************************
 * The router is responsible for dispatching requests to directly connected friend-nodes,
 * and keep track of currently forwarded requests.
 ***************************************************************************************/
class Router : IAssetSource {
private:
    ForwardedAsset[ulong] openRequests;
    Friend[Client] connectedFriends;
public:
    this() {
    }

    /************************************************************************************
     * Implements IAssetSource.find. Unless request is already under forwarding, forward
     * to all connected friends.
     ***********************************************************************************/
    ForwardedAsset findAsset(daemon.client.OpenRequest req, BHServerOpenCallback cb) {
        if (req.uuid in openRequests)
            req.callback(null, Status.WOULD_LOOP);
        else
            return forwardOpenRequest(req, cb);
    }

    /************************************************************************************
     * Assign already connected friend to this router
     ***********************************************************************************/
    void registerFriend(Friend f) {
        connectedFriends[f.c] = f;
    }

    /************************************************************************************
     * Disconnect friend from this router
     ***********************************************************************************/
    Friend unregisterFriend(Client c) {
        if (c in connectedFriends) {
            auto friend = connectedFriends[c];
            connectedFriends.remove(c);
            return friend;
        } else {
            return null;
        }
    }
private:
    /************************************************************************************
     * Remove request from list of in-flight-openRequests
     ***********************************************************************************/
    void openRequestCompleted(daemon.client.OpenRequest req) {
        this.openRequests.remove(req.uuid);
    }

    /************************************************************************************
     * Work-horse of forwarding, iterate through connected friends and send out forwarded
     * requests.
     ***********************************************************************************/
    // TODO: Exception-handling; what if sending to friend fails?
    ForwardedAsset forwardOpenRequest(daemon.client.OpenRequest req, BHServerOpenCallback cb) {
        bool forwarded = false;
        auto asset = new ForwardedAsset(req, cb, &openRequestCompleted);
        asset.takeRef();
        foreach (friend; connectedFriends) {
            auto client = friend.c;
            if (client != req.client) {
                asset.waitingResponses += 1;
                // TODO: Randomize timeouts
                client.open(req.ids, &asset.addBackingAsset, req.uuid, TimeSpan.fromMillis(req.timeout-50));
                forwarded = true;
            }
        }
        if (!forwarded) {
            asset.doCallback();
            delete asset;
            return null;
        } else {
            openRequests[req.uuid] = asset;
            return asset;
        }
    }
}