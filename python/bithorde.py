# -*- coding: utf-8 -*-
'''
Python library for querying BitHorde nodes. Currently only implements opening and closing
assets. More to come later.

Twisted-based implementation.
'''

import socket
import os, os.path
from base64 import b32decode as _b32decode
from types import MethodType

import bithorde_pb2 as message

from twisted.internet import reactor, protocol

from google.protobuf import descriptor
from google.protobuf.internal import encoder,decoder

# Protocol imports and definitions
MSGMAP = message.Stream.DESCRIPTOR.fields_by_number
MSG_REV_MAP = {
    message.HandShake:     1,
    message.BindRead:      2,
    message.AssetStatus:   3,
    message.Read.Request:  5,
    message.Read.Response: 6,
    message.BindWrite:     7,
    message.DataSegment:   8,
}

class HandleAllocator(object):
    '''Stack-like allocator for keeping track of used and unused handles.'''
    def __init__(self):
        self._reusequeue = []
        self._counter = 0

    def allocate(self):
        if len(self._reusequeue):
            return self._reusequeue.pop()
        else:
            self._counter += 1
            return self._counter

    def deallocate(self, handle):
        self._reusequeue.append(handle)

class AssetMap(list):
    '''Simple overloaded auto-growing list to map assets to their handles.'''
    def __setitem__(self, k, v):
        l = len(self)
        if l <= k:
            self.extend((None,)*((k-l)+2))
        return list.__setitem__(self, k, v)

class Connection(protocol.Protocol):
    '''Twisted-driven connection to BitHorde'''
    def connectionMade(self):
        '''!Twisted-API! Once connected, send a handshake and wait for the other
        side.'''
        self.buf = ""

    def dataReceived(self, data):
        '''!Twisted-API! When data arrives, append to buffer and try to parse into
        BitHorde-messages'''
        self.buf += data

        dataleft = True
        while dataleft:
            buf = self.buf
            try:
                id, newpos = decoder._DecodeVarint32(buf,0)
                size, newpos = decoder._DecodeVarint32(buf,newpos)
                id = id >> 3
                msgend = newpos+size
                if msgend > len(buf):
                    dataleft = False
            except IndexError:
                dataleft = False

            if dataleft:
                self.buf = buf[msgend:]
                msg = MSGMAP[id].message_type._concrete_class()
                msg.ParseFromString(buf[newpos:msgend])

                self.msgHandler(msg)

    def writeMsg(self, msg):
        '''Serialize a BitHorde-message and write to the underlying Twisted-transport.'''
        enc = encoder.MessageEncoder(MSG_REV_MAP[type(msg)], False, False)
        enc(self.transport.write, msg)

    def close(self):
        self.transport.loseConnection()

class Client(Connection):
    '''Overrides a BitHorde-connection with Client-semantics. In particular provides
    client-handle-mappings and connection-state-logic.'''
    def connectionMade(self, userName = "python_bithorde"):
        self.remoteUser = None
        self.msgHandler = self._preAuthState
        self._assets = AssetMap()
        self._handles = HandleAllocator()
        Connection.connectionMade(self)

        handshake = message.HandShake()
        handshake.name = userName
        handshake.protoversion = 1
        self.writeMsg(handshake)

    def nodeConnected(self):
        '''Event triggered once a connection has been established, and authentication is done.'''
        pass

    def allocateHandle(self, asset):
        '''Allocates a handle for the provided implementation, and assign it a handle'''
        assert(asset.handle is None)
        asset.client = self
        asset.handle = handle = self._handles.allocate()
        self._assets[handle] = asset
        return asset

    def _bind(self, asset):
        '''Try to open asset'''
        assert(self.msgHandler == self._mainState)
        assert(asset is not None)
        msg = message.BindRead()
        msg.handle = asset.handle

        for t,v in asset.hashIds.iteritems():
            id = msg.ids.add()
            id.type = t
            id.id = v
        msg.timeout = 10000
        self.writeMsg(msg)

    def _closeAsset(self, handle):
        '''Unbind an asset from this Client and notify upstream.'''
        def _cleanupCallback(status):
            assert status and status.status == message.NOTFOUND
            self._assets[handle] = None
            self._handles.deallocate(handle)
        asset = self._assets[handle]
        if asset:
            asset.handle = None
            asset.onStatusUpdate = _cleanupCallback
        msg = message.BindRead()
        msg.handle = handle
        self.writeMsg(msg)

    def _preAuthState(self, msg):
        '''Validates handshake and then changes state to _mainState'''
        if msg.DESCRIPTOR.name != "HandShake":
            print "Error: unexpected msg %s for preauth state." % msg.DESCRIPTOR.name
            self.close()
        self.remoteUser = msg.name
        self.protoversion = msg.protoversion
        self.msgHandler = self._mainState
        self.nodeConnected()

    def _mainState(self, msg):
        '''The main msg-reaction-routine, used after handshake.'''
        if isinstance(msg, message.AssetStatus):
            asset = self._assets[msg.handle]
            if asset:
                asset.onStatusUpdate(msg)

class Asset(object):
    '''Base-implementation of a BitHorde asset. For practical purposes, subclass and
    override onStatusUpdate.

    An asset have 4 states.
    1. "Created"
    2. "Allocated" through Client.allocateHandle
    3. "Bound" after call to bind. In this stage, the asset recieves statusUpdates.
    4. "Closed" after call to close
    '''
    def __init__(self):
        '''Creates a new Asset, unbound to any particular client instance.'''
        self.handle = None

    def bind(self, hashIds):
        '''Binds the asset to the provided hashIds'''
        self.hashIds = hashIds
        self.client._bind(self)

    def close(self):
        '''Closes the asset.'''
        assert(self.client and self.handle)
        self.client._closeAsset(self.handle)

    def onStatusUpdate(self, status):
        '''Should probably be overridden in subclass to react to status-changes.'''
        pass

class AssetIterator(object):
    '''Helper to iterate some assets, trying to open them, and fire a callback for each
       asset. See exampel in __main__ part of module.'''
    def __init__(self, client, assets, callback, whenDone, parallel=10):
        self.client = client
        self.assets = assets
        self.callback = callback
        self.whenDone = whenDone
        self.parallel = parallel
        self.requestCount = 0
        self._request()

    def _request(self):
        while self.requestCount < self.parallel:
            try:
                key, hashIds = self.assets.next()
            except StopIteration:
                return

            asset = Asset()
            asset.key = key
            asset.onStatusUpdate = MethodType(self._gotResponse, asset, Asset)
            self.client.allocateHandle(asset)
            asset.bind(hashIds)

            self.requestCount += 1

    def _gotResponse(self, asset, status):
        Asset.onStatusUpdate(asset, status)
        result = self.callback(asset, status, asset.key)

        if not result:
            asset.close()

        self.requestCount -= 1
        self._request() # Request more, if needed

        if not self.requestCount:
            self.whenDone()

class ClientFactory(protocol.ClientFactory):
    '''!Twisted-API! Twisted-factory for creating Client-instances for new connections.

    You will most likely want to subclass and override clientConnectionFailed and
    clientConnectionLost.
    '''
    def __init__(self, c):
        self.protocol = c

def b32decode(string):
    l = len(string)
    string = string + "="*(7-((l-1)%8)) # Pad with = for b32decodes:s pleasure
    return _b32decode(string, True)

def connectUNIX(sock, callback, failCallback, *args, **kwargs):
    def onConnection(client):
        Client.nodeConnected(client)
        callback(client, *args, **kwargs)
    def createClient():
        client = Client()
        client.nodeConnected = MethodType(onConnection, client, Client)
        return client
    factory = ClientFactory(createClient)
    factory.clientConnectionFailed = lambda _,reason: failCallback(reason.getErrorMessage())
    reactor.connectUNIX(sock, factory)

if __name__ == '__main__':
    import sys

    def onStatusUpdate(asset, status, key):
        print "Asset status: %s, %s" % (key, message._STATUS.values_by_number[status.status].name)

    def onClientConnected(client, assetIds):
        ai = AssetIterator(client, assetIds, onStatusUpdate, whenDone)

    def onClientFailed(reason):
        print "Failed to connect to BitHorde; '%s'" % reason
        reactor.stop()

    def whenDone():
        reactor.stop()

    if len(sys.argv) > 1:
        assetIds = ((asset,{message.TREE_TIGER: b32decode(asset)}) for asset in sys.argv[1:])
        connectUNIX("/tmp/bithorde", onClientConnected, onClientFailed, assetIds)
        reactor.run()
    else:
        print "Usage: %s <tiger tree hash: base32> ..." % sys.argv[0]

