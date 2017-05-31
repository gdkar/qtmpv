import weakref
import argparse
import functools
import pathlib
import ctypes
import struct, array
import os
import sys
import pprint
import time
import collections
from qtproxy import Q

import av
import mpv
import av_player

class TreeItem(object):
    def __init__(self, name, player=None, parent=None):
        self._parent= parent
        if parent is not None:
            parent.appendChild(self)
        self._name = name
        self._children   = list()
        self._player     = weakref.ref(player) if player else None

    @property
    def player(self):
        return self._player()

    def findData(self, value, column=0):
        for child in self._children:
            if child and child.data(column) == value:
                return child
    def appendChild(self, item):
        if item in self._children:
            self._children.remove(item)
        self._children.append(item)
    def child(self, row):
        return self._children[row]
    def childCount(self):
        return len(self._children)
    def columnCount(self):
        return 2
    def setData(self, column, data):
        if column == 0:
            self._name = data
            return True
        else:
            return False

    def data(self, column):
        if column is 0:
            return self._name
    def parent(self):
        return self._parent
    def row(self):
        if self._parent:
            return self._parent._children.index(self)
        return 0

class LeafItem(TreeItem):
    def __init__(self, name, attr, player=None, parent=None):
        super().__init__(name, player, parent)
        if isinstance(attr,str):
            try:
                attr = player.get_property(attr)
            except:
                attr = None
        self._attr = attr
    def setData(self, column, data):
        if column == 1 and self._attr:
            try:
                self._attr.setValue(data)
                return True
            except:pass
        return super().setData(column,data)
    def data(self, column):
        if column == 1:
            if self._attr:
                return self._attr.value()
        return super().data(column)
    def columnCount(self):
        return 2

class AVTreePropertyModel(Q.QAbstractItemModel):
    def __init__(self, *args, **kwargs):
        player = kwargs.pop('player', None)
        self._player = player
        super().__init__(*args, **kwargs)
        self._headerData = ["name","value"]
        self._rootItem = TreeItem(name='root',player=player)
        self.setupModelData(player)
        print (self.__class__.__name__, 'rowCount() is ', self.rowCount(Q.QModelIndex()))
    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return len(self._headerData)
    def setData(self, index, value, role):
        if not index.isValid():
            return False
        item = index.internalPointer()
        if item:
            return item.setData(index.column(), value)
        else:
            return False
    def data(self, index, role):
        if not index.isValid():
            return None
        if role not in (Q.Qt.DisplayRole, Q.Qt.EditRole):
            return None
        item = index.internalPointer()
        return item.data(index.column())

    def flags(self, index):
        if not index.isValid():
            return Q.Qt.NoItemFlags
        if index.column() == 1:
            return Q.Qt.ItemIsEnabled|Q.Qt.ItemIsSelectable|Q.Qt.ItemIsEditable
        else:
            return Q.Qt.ItemIsEnabled|Q.Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        if orientation == Q.Qt.Horizontal and role == Q.Qt.DisplayRole:
            return self._headerData[section]
    def index(self, row, column, parent):
        if not self.hasIndex(row,column,parent):
            return Q.QModelIndex()
        if not parent.isValid():
            parentItem = self._rootItem
        else:
            parentItem = parent.internalPointer()
        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row,column,childItem)
        else:
            return Q.QModelIndex()
    def indexForItem(self, item, column = 0):
        return self.createIndex(item.row(), column, item)
    def parent(self, index):
        if not index.isValid():
            return Q.QModelIndex()
        childItem = index.internalPointer()
        parentItem = childItem.parent()
        if parentItem is self._rootItem:
            return Q.QModelIndex()
        return self.indexForItem(parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0
        if parent.isValid():
            parentItem = parent.internalPointer()
        else:
            parentItem = self._rootItem
        return parentItem.childCount()

    def setupModelData(self, player):
        def lcp(a,b):
            if not a or not b:
                return 0
            for n, (ai,bi) in enumerate(zip(a,b)):
                if ai != bi: return n
            return n+1
        def layer(parts, proot, prefix):
#            if len(parts) == 1 and parts[0][0] is not prefix:
#                layer(parts,proot,parts[0][0])
            root = None
            if len(parts) == 1:
                part = parts[0]
                root = LeafItem(name=part.objectName(), attr=part, player=player,parent=proot)
                return
            if len(parts)==0:
                return

            if prefix is None:
                root = proot
            if len(parts) == 1:
                common = len(parts[0].objectName())
            else:
                common = min(lcp(i0.objectName().split('-'),i1.objectName().split('-')) for i0,i1 in zip(parts,parts[1:]))
                common = len('-'.join(parts[0].objectName().split('-')[:common]))
            prefix = parts[0].objectName()[:common]
            if not root:
                root = TreeItem(name=prefix,player=player,parent=proot)
            sub = dict()
            for part in parts:
                name = part.objectName()
                sindex = name.find('-',common + 1)
                sprefix = name[:sindex] if sindex > 0 else name
                if sprefix in sub:
                    sub[sprefix].append(part)
                else:
                    sub[sprefix] = [part]
            for k in sorted(sub.keys()):
                layer(sub[k], proot=root, prefix=k)
        props = sorted(list(set(player.m.attr_name(_) for _ in player.m.properties|player.m.options)))
        parts = [player.get_property(_) for _ in props]
        parts = [_ for _ in parts if _ is not None]

        layer(parts, self._rootItem, None )
class PropertyGroup:
    def __init__(self, prefix, suffixes, player, parent=None):
        def combine(*args):
            return '-'.join(filter(None, args))
        if parent is not None:
            self._parent = weakref.ref(parent)
        else:
            self._parent = None
        self._player = weakref.ref(player)
        self._prefix = prefix
        self._children = list()
        self._property = None
        self._name = _name = ''
        if not suffixes:
            try:
                self._property = getattr(player, player.m.attr_name(prefix))
            except:
                pass
            return
        kids = {'': set(suffixes)}
        vals = dict()
        while len(kids) == 1:
            k, suffs = next(iter(kids.items()))
            kids = dict()
#            if not vals:
            prefix = combine(prefix,k)
            _name = combine(_name, k)
            k = ''
            for s in suffs:
                pre, _, suf = s.partition('-')
                if suf:
                    kids.setdefault(combine(k,pre), set()).add(suf)
                else:
                    full = combine(prefix,k, pre)
                    vals[combine(k,pre)] = set()
        self._prefix = prefix
        self._name   = _name
        kids.update(vals)
        for k,v in sorted(kids.items()):
            self._children.append(PropertyGroup(combine(prefix, k), v, player, parent=self))
