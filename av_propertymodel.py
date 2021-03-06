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

#import av
import mpv
import av_player

class TreeItem(object):
    def __init__(self, name, player=None, parent=None, model=None):
        self._parent= weakref.ref(parent) if parent else None
        if parent is not None:
            parent.appendChild(self)
        self._model = model
        self._name = name
        self._children   = list()
        self._player     = weakref.ref(player) if player else None

    @property
    def player(self):
        if self._player is not None:
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

    @property
    def parent(self):
        if self._parent is not None:
            return self._parent()

    def row(self):
        parent = self.parent
        if parent:
            try:
                return parent._children.index(self)
            except:
                pass
        return 0

class LitItem(TreeItem):
    def __init__(self, name, val, player=None, parent=None,model=None):
        super().__init__(name, player=player,parent=parent,model=model)
#        print('creating LitItem',name,val)
        self._val = None
        if isinstance(val, list):
            for n,_sub in enumerate(val):
                LitItem(name = name+'/{}'.format(n),val=_sub, player=player,parent=self, model=model)
        elif isinstance(val, dict):
            for k,v in val.items():
                LitItem(name = name+'/{}'.format(k),val=v,player=player,parent=self,model=model)
        else:
            self._val = val

    def setData(self, column, data):
        return super().setData(column,data)

    def data(self, column):
        if column == 1:
            return self._val

        return super().data(column)

    def columnCount(self):
        return 2

class LeafItem(TreeItem):
    def __init__(self, name, attr, player=None, parent=None, model=None):
        super().__init__(name, player, parent, model)
        self._val = None
        self._prop = None
        self._attr = attr
        if isinstance(attr,av_player.AVProperty):
            self._prop = attr
            self._attr = self._prop.objectName()
        else:
            try:
                self._prop = player.get_property(attr)
                if not isinstance(self._prop, av_player.AVProperty):
                    self._prop = None
                else:
                    print(self._prop)
            except:
                self._prop  = None
        if self._prop is not None:
            self._bind_av_property(self._prop)
#            self._prop.valueChanged.connect(self._update)
#            if model is not None:
#                index = model.indexForItem(item = self, column=1)
#                self._prop.valueChanged.connect(lambda:model.dataChanged.emit(index,index))

        self._attr = attr

    def _bind_av_property(self, prop):
        if prop is not None:
            prop.valueChanged.connect(self._update)
            prop_ref = weakref.ref(prop)
            def _disconnect(self):
                prop = prop_ref()
                if prop:
                    try:prop.valueChanged.disconnect(self._update)
                    except:pass
                    try:prop.destroyed.disconnect(self._detach)
                    except:pass
            self._finalizer = weakref.finalize(self, _disconnect, self)
            prop.destroyed.connect(self._detach,Q.Qt.DirectConnection)
    def _detach(self):
        self._finalizer.detach()
    def _update(self):
        if self._prop is None:
            if self.player and self._attr:
                try:
                    self._prop = self.player.get_property(self._attr)
                    print(self._prop)
#                    else:
#                        print(self._prop)
                except:
                    pass
#                    self._prop  = None
            if self._prop is not None:
                self._bind_av_property(self._prop)
#                self._prop.valueChanged.connect(self._update)
#                    self._prop.valueChanged.connect(lambda:model.dataChanged.emit(index,index))
        if self._prop is not None:
            _val = self._prop.value()
        else:
            return
        if self._val is None or _val != self._val:
            self._val = _val
            model = self._model
            has_children = self._model and self._children
#            while self._children:
#                _ = self._children.pop(0)
#                _._parent = None
#                _._player = None
            if model:
                idx = model.indexForItem(self, 0)
                if len(self._children):
                    model.beginRemoveRows(idx, 0, len(self._children))
                    self._children.clear()
                    model.endRemoveRows()
            if isinstance(_val, (list,dict)):
                if model:
                    model.beginInsertRows(idx, 0, len(_val))
                if isinstance(_val, list):
                    for n,_sub in enumerate(_val):
                        LitItem(name = self._name+'/{}'.format(n),val=_sub, player=self.player,parent=self, model=self._model)
                elif isinstance(_val, dict):
                    for k,v in _val.items():
                        LitItem(name = self._name+'/{}'.format(k),val=v,player=self.player,parent=self,model=self._model)
                if model:
                    model.endInsertRows()
#            if has_children:
#                self._model.layoutChanged.emit()
            elif model:
#                index_lo = model.index(row = self.row() + 1, column=1,parent=model.parent(index_hi))
                model.dataChanged.emit(idx,idx)


    def setData(self, column, data):
        if column == 1 and self._attr:
            try:
                self._attr.setValue(data)
                return True
            except:
                pass
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
        if not index:
            return Q.QModelIndex()
        if not index.isValid():
            return Q.QModelIndex()
        childItem = index.internalPointer()
        if not childItem:
            return Q.QModelIndex()

        parentItem = childItem.parent
        if not parentItem:
            return Q.QModelIndex()
        if parentItem is self._rootItem:
            return Q.QModelIndex()
        return self.indexForItem(parentItem)

    def rowCount(self, parent):
        if parent is None:
            return
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
                root = LeafItem(name=part.objectName(), attr=part, player=player,parent=proot, model=self)
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
                root = TreeItem(name=prefix,player=player,parent=proot, model=self)
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
