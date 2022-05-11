# -*- coding: utf-8 -*-

# Copyright (C) 2012-2015 Stéphane Graber
# Author: Stéphane Graber <stgraber@ubuntu.com>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You can find the license on Debian systems in the file
# /usr/share/common-licenses/GPL-2

from fnmatch import translate
from time import process_time_ns
from urllib import parse
import ldap
from flask import Flask, abort, flash, g, redirect, render_template, request
from flask_wtf import FlaskForm
from libs.common import get_objclass
from libs.common import iri_for as url_for
from libs.common import namefrom_dn
from libs.ldap_func import (ldap_auth, ldap_delete_entry, ldap_get_entries,
                            ldap_get_group, ldap_get_ou, ldap_get_user,
                            ldap_in_group, ldap_obj_has_children, ldap_update_attribute, move)
from settings import Settings
from wtforms import SelectField, StringField, SubmitField


class FilterTreeView(FlaskForm):
    filter_str = StringField()
    filter_select = SelectField(choices=Settings.SEARCH_ATTRS)
    search = SubmitField('Search')


class BatchDelete(FlaskForm):
    delete = SubmitField('Delete Selection')

class BatchPaste(FlaskForm):
    paste = SubmitField('Paste Selection')


class BatchMoveToRoot(FlaskForm):
    toRoot = SubmitField("Move To Root")


class BatchMoveOneLevelUp(FlaskForm):
    up_aLevel = SubmitField("Move One Level Up")

def init(app):
    @app.route('/tree', methods=['GET', 'POST'])
    @app.route('/tree/<base>', methods=['GET', 'POST'])
    @ldap_auth("Domain Users")
    def tree_base(base=None):
        if not base:
            base = g.ldap['dn']
        elif not base.lower().endswith(g.ldap['dn'].lower()):
            base += ",%s" % g.ldap['dn']

        admin = ldap_in_group(Settings.ADMIN_GROUP)

        parent = None
        base_split = base.split(',')
        if not base_split[0].lower().startswith("dc"):
            parent = ",".join(base_split[1:])

        if not admin:
            abort(401)
        else:
            entry_fields = [('name', "Name"),
                            ('__description', u"Login/Description")]
            
            if Settings.TREE_ATTRIBUTES:
                for item in Settings.TREE_ATTRIBUTES:
                    entry_fields.append((item[0], item[1])) 

            form = FilterTreeView(request.form)
            batch_delete = BatchDelete()
            batch_paste = BatchPaste()
            batch_moveToRoot = BatchMoveToRoot()
            batch_moveOneLevelUp = BatchMoveOneLevelUp()

            if form.search.data and form.validate():
                filter_str = form.filter_str.data
                filter_select = form.filter_select.data
                scope = "subtree"
                entries = get_entries(filter_str, filter_select, base, scope)     
            else:
                filter_str = None
                scope = "onelevel"
                entries = get_entries("top", "objectClass", base, scope)
            
           #TODO: batch delete confirmation page
           ##batch delete
            if batch_delete.delete.data:
                checkedData = request.form.getlist("checkedItems") #returns an array of Strings, tho the strings have dict format
                toDelete = translation(checkedData)
                try:
                    deleted_list = delete_batch(toDelete)
                    flash_amount(deleted_list, deleted=True)
                except ldap.LDAPError as e:
                    flash(e,"error")
                return redirect(url_for('tree_base', base=base))
            ##batch move (1 in)
            elif batch_paste.paste.data:
                checkedData = request.form.getlist("checkedItems")
                moveTo = request.form.get("moveHere")
                moveTo = parse.unquote(moveTo.split("tree/")[1].split(",")[0])
                toMove = translation(checkedData)
                try:
                    moved_list = move_batch(toMove,moveTo)
                    flash_amount(moved_list,deleted=False)
                except ldap.LDAPError as e:
                    e = dict(e.args[0])
                    flash(e['info'], "error")
                return redirect(url_for('tree_base', base=base))
            ##batch move (to root)
            # elif batch_moveToRoot.toRoot.data:
            #     checkedData = request.form.getlist("checkedItems")
            #     moveTo = "" #root ??
            #     print(checkedData)
            #     toMove = translation(checkedData)
            #     try:
            #         moved_list = move_batch(toMove,moveTo)
            #         flash_amount(moved_list, deleted=False)
            #     except ldap.LDAPError as e:
            #         e = dict(e.args[0])
            #         flash(e['info'], "error")
            #     return redirect(url_for('tree_base'))
            ##batch move (1 out)
            elif batch_moveOneLevelUp.up_aLevel.data:
                checkedData = request.form.getlist("checkedItems")
                moveTo = parse.unquote(parent.split(",")[0])
                toMove = translation(checkedData)
                try:
                    moved_list = move_batch(toMove,moveTo)
                    flash_amount(moved_list, deleted=False)
                    pass
                except ldap.LDAPError as e:
                    e = dict(e.args[0])
                    flash(e['info'], "error")
                return redirect(url_for('tree_base', base=base))

        name = namefrom_dn(base)
        objclass = get_objclass(base)
        return render_template("pages/tree_base_es.html", form=form, parent=parent, batch_delete=batch_delete,
                                batch_paste=batch_paste,batch_moveOneLevelUp=batch_moveOneLevelUp,batch_moveToRoot=batch_moveToRoot,
                                admin=admin, base=base.upper(), entries=entries,entry_fields=entry_fields, 
                               root=g.ldap['search_dn'].upper(), name=name, objclass=objclass)

    def get_entries(filter_str, filter_select, base, scope):
        """
        Get all entries that will be displayed in the tree
        """
        entries = []

        users = ldap_get_entries("objectClass=top", base, scope, ignore_erros=True)
        users = filter(lambda entry: 'displayName' in entry, users)
        users = filter(lambda entry: 'sAMAccountName' in entry, users)
        users = filter(lambda entry: filter_select in entry, users)
        users = filter(lambda entry: filter_str in entry[filter_select], users)
        users = sorted(users, key=lambda entry: entry['displayName'])
        if filter_str == "top":
            other_entries = ldap_get_entries("objectClass=top", base, scope, ignore_erros=True)
            other_entries = filter(lambda entry: 'displayName' not in entry, other_entries)
            other_entries = sorted(other_entries, key=lambda entry: entry['name'])
        else:
            other_entries = []
        for entry in users:
            if 'description' not in entry:
                if 'sAMAccountName' in entry:
                   entry['__description'] = entry['sAMAccountName']
            else:
                entry['__description'] = entry['description']

            entry['__target'] = url_for('tree_base', base=entry['distinguishedName'])

            entry['name'] = entry['displayName']
            entry['__type'] = "User"
            entry['__target'] = url_for('user_overview', username=entry['sAMAccountName'])

            if 'user' in entry['objectClass']:
                if entry['userAccountControl'] == 2:
                    entry['active'] = "Deactivated"
                else:
                    entry['active'] = "Active"
            else:
                entry['active'] = "No available"

            if 'showInAdvancedViewOnly' in entry and entry['showInAdvancedViewOnly']:
                continue
            entries.append(entry)

        for entry in other_entries:
            if entry not in users:
                if 'description' not in entry:
                    if 'sAMAccountName' in entry:
                        entry['__description'] = entry['sAMAccountName']
                else:
                    entry['__description'] = entry['description']

                entry['__target'] = url_for('tree_base', base=entry['distinguishedName'])

                if 'group' in entry['objectClass']:
                    entry['__type'] = "Group"
                    entry['__target'] = url_for('group_overview',
                                                groupname=entry['sAMAccountName'])
                elif 'organizationalUnit' in entry['objectClass']:
                    entry['__type'] = "Organization Unit"
                elif 'container' in entry['objectClass']:
                    entry['__type'] = "Container"
                elif 'builtinDomain' in entry['objectClass']:
                    entry['__type'] = "Built-in"
                # Hacky solution for when there is Person objects that do not have displayName and can be misclassified
                # TODO: Probably a good indication that is time to refactor this mess
                elif 'person' in entry['objectClass']:
                    entry['__type'] = "User"
                    entry['__target'] = url_for('user_overview', username=entry['sAMAccountName'])
                else:
                    entry['__type'] = entry['objectClass'][1]
                entries.append(entry)
                for blacklist in Settings.TREE_BLACKLIST:
                    if entry['distinguishedName'].startswith(blacklist):
                        entries.remove(entry)
                        translation
        return entries

    def translation(checkedData:list):
        '''
        recieves a list of strings with format 
        ``["{name:<>, type:<>, target:<>}",...]`` \n
        and translates them into dicts with keys: 
        ``name``, ``type``, ``username``(except if type is Organization Unit), and ``dn``;
        extracted from those string
        and returns them in a new list
        '''

        translated = []
        for x in checkedData:
            dicts = {}
            key1 = x.split("name:'")[1].split("'")[0] #name of the object
            key2 = x.split("type:'")[1].split("'")[0] #User, Group, Organization Unit
            key3 = x.split("target:'")[1].replace("'}", "")
            key4 = key3.split("/")[2] #username
            if key2 == "User":
                user = ldap_get_user(username=key4)
                key5 = user['distinguishedName']
            elif key2 == "Group":
                group = ldap_get_group(groupname=key1)
                key5 = group['distinguishedName']
            elif key2 == "Organization Unit":
                key5 = parse.unquote(key4)
            dicts['name'] = key1
            dicts['type'] = key2
            if key2 != 'Organization Unit':
                dicts['username'] = key4
            dicts['dn'] = key5
            translated.append(dicts)
        return translated
    
    def delete_batch(translatedList:list):
        """
        Deletes the objects in the ``translatedList`` and saves the names of each element on a list to be returned
        OU objects with children will not be deleted and will have an error flash
        \n
        recieves a ``translatedList`` with the format returned by ``translation()``
        \n
        Return: a list with the names of the deleted elements
        """
        deleted_list=[]
        for obj in translatedList:
            #since now there is a dn key there is no need to check what type is the current element to user the
            #ldap_get_ou(), ldap_get_user(), ldap_get_group() just to get their dn
            if obj['type'] != "Organization Unit":
                ldap_delete_entry(obj['dn'])
                deleted_list.append(obj['name'])
            else:
                canDelete = not ldap_obj_has_children(obj['dn'])
                if canDelete:
                    ldap_delete_entry(obj['dn'])
                    deleted_list.append(obj['name'])
                else:
                    flash(f"Can't delete OU: '{obj['name']}' because is not empty", "error")
        return deleted_list

    def move_batch(translatedList: list, moveTo: str):
        """moves the elements from the list to the selected OU

        Args:
            translatedList (list): _description_
            moveTo (str): _description_

        Returns:
            a list with the names of the moved elements
        """
        moved_list = []
        for obj in translatedList:
            moved_list.append(obj['name'])
            ldap_update_attribute(dn=obj["dn"], attribute="distinguishedName", value=obj["dn"].split(",")[0], new_parent=moveTo)
            #since now there is a dn key there is no need to check what type is the current element to user the 
            #ldap_get_ou(), ldap_get_user(), ldap_get_group() just to get their dn
        return moved_list
    
    def flash_amount(namesList:list, deleted:bool):
        """
        flashes how many elements were moved/deleted
        recieves the list returned by ``move_batch()`` or ``delete_batch()`` and an extra argument to know if elements were moved or deleted
        """
        if deleted:
            action = "deleted"
        else:
            action = "moved"
        if len(namesList):
            if len(namesList) == 1:
                flash("1 element "+ action+ " successfully.", "success")
            else:
                flash(f"{len(namesList)} elements " +action+ " successfully", "success")
