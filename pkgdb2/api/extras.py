# -*- coding: utf-8 -*-
#
# Copyright © 2013-2015  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions
# of the GNU General Public License v.2, or (at your option) any later
# version.  This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.  You
# should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Any Red Hat trademarks that are incorporated in the source
# code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission
# of Red Hat, Inc.
#

'''
Extras API endpoints for the Flask application.
'''

import flask
import requests

import pkgdb2.lib as pkgdblib
from pkgdb2 import SESSION, APP
from pkgdb2.api import API


def request_wants_json():
    """ Return weather a json output was requested. """
    best = flask.request.accept_mimetypes \
        .best_match(['application/json', 'text/html'])
    return best == 'application/json' and \
        flask.request.accept_mimetypes[best] > \
        flask.request.accept_mimetypes['text/html']


#@pkgdb.CACHE.cache_on_arguments(expiration_time=3600)
def _bz_acls_cached(name=None, out_format='text'):
    '''Return the package attributes used by bugzilla.

    :kwarg collection: Name of the bugzilla collection to gather data on.
    :kwarg out_format: Specify if the output if text or json.

    Note: The data returned by this function is for the way the current
    Fedora bugzilla is setup as of (2007/6/25).  In the future, bugzilla
    may change to have separate products for each collection-version.
    When that happens we'll have to change what this function returns.

    The returned data looks like this:

    bugzillaAcls[collection][package].attribute
    attribute is one of:
        :owner: FAS username for the owner
        :qacontact: if the package has a special qacontact, their userid
            is listed here
        :summary: Short description of the package
        :cclist: list of FAS userids that are watching the package
    '''

    packages = pkgdblib.bugzilla(
        session=SESSION,
        name=name)

    output = []
    if out_format == 'json':
        output = {'bugzillaAcls': {},
                  'title': 'Fedora Package Database -- Bugzilla ACLs'}

    for clt in sorted(packages):
        for pkg in sorted(packages[clt]):
            if out_format == 'json':
                user = []
                group = []
                for ppl in packages[clt][pkg]['cc'].split(','):
                    if ppl.startswith('group::'):
                        group.append(ppl.replace('group::', '@').encode('UTF-8'))
                    elif ppl:
                        user.append(ppl.encode('UTF-8'))
                poc = packages[clt][pkg]['poc']
                if poc.startswith('group::'):
                    poc = poc.replace('group::', '@')

                if clt not in output['bugzillaAcls']:
                    output['bugzillaAcls'][clt.encode('UTF-8')] = {}

                output['bugzillaAcls'][clt][pkg.encode('UTF-8')] = {
                    'owner': poc.encode('UTF-8'),
                    'cclist': {
                        'groups': group,
                        'people': user,
                    },
                    'qacontact': None,
                    'summary': packages[clt][pkg]['summary'].encode('UTF-8')
                }
            else:
                output.append(
                    '%(collection)s|%(name)s|%(summary)s|%(poc)s|%(qa)s'
                    '|%(cc)s' % (packages[clt][pkg])
                )
    return output


#@pkgdb.CACHE.cache_on_arguments(expiration_time=3600)
def _bz_notify_cache(
        name=None, version=None, eol=False, out_format='text', acls=None):
    '''List of usernames that should be notified of changes to a package.

    For the collections specified we want to retrieve all of the owners,
    watchbugzilla, and watchcommits accounts.

    :kwarg name: Set to a collection name to filter the results for that
    :kwarg version: Set to a collection version to further filter results
        for a single version
    :kwarg eol: Set to True if you want to include end of life
        distributions
    :kwarg out_format: Specify if the output if text or json.
    '''
    packages = pkgdblib.notify(
        session=SESSION,
        eol=eol,
        name=name,
        version=version,
        acls=acls)
    output = []
    if out_format == 'json':
        output = {'packages': {},
                  'eol': eol,
                  'name': name,
                  'version': version,
                  'title': 'Fedora Package Database -- Notification List'}
    for package in sorted(packages):
        if out_format == 'json':
            output['packages'][package] = packages[package].split(',')
        else:
            output.append('%s|%s\n' % (package, packages[package]))
    return output


#@pkgdb.CACHE.cache_on_arguments(expiration_time=3600)
def _vcs_acls_cache(out_format='text', eol=False):
    '''Return ACLs for the version control system.

    :kwarg out_format: Specify if the output if text or json.
    :kwarg eol: A boolean specifying whether to include information about
        End Of Life collections or not. Defaults to ``False``.

    '''
    packages = pkgdblib.vcs_acls(
        session=SESSION, eol=eol, oformat=out_format,
        skip_pp=APP.config.get('PKGS_NOT_PROVENPACKAGER', None))
    output = []
    if out_format == 'json':
        output = {'packageAcls': packages,
                  'title': 'Fedora Package Database -- VCS ACLs'}
    else:
        for package in sorted(packages):
            for branch in sorted(packages[package]):
                if packages[package][branch]['group']:
                    packages[package][branch]['group'] += ','
                output.append(
                    'avail | %(group)s%(user)s | rpms/%(name)s/%(branch)s'
                    % (packages[package][branch]))
    return output


@API.route('/bugzilla/')
@API.route('/bugzilla')
def api_bugzilla():
    '''
Bugzilla information
--------------------
    Return the package attributes used by bugzilla.

    ::

        /api/bugzilla

    :karg collection: Name of the bugzilla collection to gather data on.
    :kwarg format: Specify if the output if text or json.

    Note: The data returned by this function is for the way the current
    Fedora bugzilla is setup as of (2007/6/25).  In the future, bugzilla
    may change to have separate products for each collection-version.
    When that happens we'll have to change what this function returns.

    The returned data looks like this::

        bugzillaAcls[collection][package].attribute

    attribute is one of:

    :owner: FAS username for the owner
    :qacontact: if the package has a special qacontact, their userid
        is listed here
    :summary: Short description of the package
    :cclist: list of FAS userids that are watching the package

    '''

    name = flask.request.args.get('collection', None)
    out_format = flask.request.args.get('format', 'text')
    if out_format not in ('text', 'json'):
        out_format = 'text'

    if request_wants_json():
        out_format = 'json'

    intro = r"""# Package Database VCS Acls
# Text Format
# Collection|Package|Description|Owner|Initial QA|Initial CCList
# Backslashes (\) are escaped as \u005c Pipes (|) are escaped as \u007c

"""

    acls = _bz_acls_cached(name, out_format)

    if out_format == 'json':
        return flask.jsonify(acls)
    else:
        return flask.Response(
            intro + "\n".join(acls),
            content_type="text/plain;charset=UTF-8"
        )


@API.route('/notify/')
@API.route('/notify')
def api_notify():
    '''
    Notification information
    ------------------------
    List of usernames that have commit or approveacls ACL for each package.

    ::

        /api/notify

    For the collections specified retrieve all of the users having at least
    one of the following ACLs for each package: commit, approveacls.

    :kwarg name: Set to a collection name to filter the results for that
    :kwarg version: Set to a collection version to further filter results
        for a single version
    :kwarg eol: Set to True if you want to include end of life
        distributions
    :kwarg format: Specify if the output if text or json.
    '''

    name = flask.request.args.get('name', None)
    version = flask.request.args.get('version', None)
    eol = flask.request.args.get('eol', False)
    out_format = flask.request.args.get('format', 'text')
    if out_format not in ('text', 'json'):
        out_format = 'text'

    if request_wants_json():
        out_format = 'json'

    output = _bz_notify_cache(
        name, version, eol, out_format,
        acls=['commit', 'approveacls', 'watchcommits'])

    if out_format == 'json':
        return flask.jsonify(output)
    else:
        return flask.Response(
            output,
            content_type="text/plain;charset=UTF-8"
        )


@API.route('/notify/all/')
@API.route('/notify/all')
def api_notify_all():
    '''
    Notification information 2
    --------------------------
    List of usernames that should be notified of changes to a package.

    ::

        /api/notify/all

    For the collections specified we want to retrieve all of the users,
    having at least one ACL for each package.

    :kwarg name: Set to a collection name to filter the results for that
    :kwarg version: Set to a collection version to further filter results
        for a single version
    :kwarg eol: Set to True if you want to include end of life
        distributions
    :kwarg format: Specify if the output if text or json.
    '''

    name = flask.request.args.get('name', None)
    version = flask.request.args.get('version', None)
    eol = flask.request.args.get('eol', False)
    out_format = flask.request.args.get('format', 'text')
    if out_format not in ('text', 'json'):
        out_format = 'text'

    if request_wants_json():
        out_format = 'json'

    output = _bz_notify_cache(name, version, eol, out_format, acls='all')

    if out_format == 'json':
        return flask.jsonify(output)
    else:
        return flask.Response(
            output,
            content_type="text/plain;charset=UTF-8"
        )


@API.route('/vcs/')
@API.route('/vcs')
def api_vcs():
    '''
    Version Control System ACLs
    ---------------------------
    Return ACLs for the version control system.

    ::

        /api/vcs

    :kwarg format: Specify if the output if text or json.
    :kwarg eol: A boolean specifying whether to include information about
        End Of Life collections or not. Defaults to ``False``.

    '''
    intro = """# VCS ACLs
# avail|@groups,users|rpms/Package/branch

"""

    out_format = flask.request.args.get('format', 'text')
    eol = flask.request.args.get('eol', False)

    if out_format not in ('text', 'json'):
        out_format = 'text'

    if request_wants_json():
        out_format = 'json'

    acls = _vcs_acls_cache(out_format, eol=eol)

    if out_format == 'json':
        return flask.jsonify(acls)
    else:
        return flask.Response(
            intro + "\n".join(acls),
            content_type="text/plain;charset=UTF-8"
        )


@API.route('/critpath/')
@API.route('/critpath')
def api_critpath():
    '''
    Critical path packages
    ----------------------
    Return the list of package marked as critpath for some or all active
    releases of fedora.

    ::

        /api/critpath

    :kwarg branches: Return the list of packages marked as critpath in the
        specified branch(es).
    :kwarg format: Specify if the output if text or json.

    '''

    out_format = flask.request.args.get('format', 'text')
    branches = flask.request.args.getlist('branches')

    if out_format not in ('text', 'json'):
        out_format = 'text'

    if request_wants_json():
        out_format = 'json'

    output = {}

    if not branches:
        active_collections = pkgdblib.search_collection(
            SESSION, '*', status='Under Development')
        active_collections.extend(
            pkgdblib.search_collection(SESSION, '*', status='Active'))
    else:
        active_collections = []
        for branch in branches:
            active_collections.extend(
                pkgdblib.search_collection(SESSION, branch)
            )

    for collection in active_collections:
        if collection.name != 'Fedora':
            continue
        pkgs = pkgdblib.get_critpath_packages(
            SESSION, branch=collection.branchname)
        if not pkgs:
            continue
        output[collection.branchname] = [pkg.package.name for pkg in pkgs]

    if out_format == 'json':
        output = {"pkgs": output}
        return flask.jsonify(output)
    else:
        output_str = []
        keys = output.keys()
        keys.reverse()
        for key in keys:
            output_str.append("== %s ==\n" % key)
            for pkg in output[key]:
                output_str.append("* %s\n" % pkg)
        return flask.Response(
            ''.join(output_str),
            content_type="text/plain;charset=UTF-8"
        )


@API.route('/pendingacls/')
@API.route('/pendingacls')
def api_pendingacls():
    '''
    Pending ACLs requests
    ---------------------
    Return the list ACLs request that are ``Awaiting Approval``.

    ::

        /api/pendingacls

    :kwarg username: Return the list of pending ACL requests requiring
        action from the specified user.
    :kwarg format: Specify if the output if text or json.

    '''

    out_format = flask.request.args.get('format', 'text')
    username = flask.request.args.get('username', None)

    if out_format not in ('text', 'json'):
        out_format = 'text'

    if request_wants_json():
        out_format = 'json'

    output = {}

    pending_acls = pkgdblib.get_pending_acl_user(
        SESSION, username)

    if out_format == 'json':
        output = {"pending_acls": pending_acls}
        output['total_requests_pending'] = len(pending_acls)
        return flask.jsonify(output)
    else:
        pending_acls.sort(key=lambda it: it['package'])
        output = [
            "# Number of requests pending: %s" % len(pending_acls)]
        for entry in pending_acls:
            output.append(
                "%(package)s:%(collection)s has %(user)s waiting for "
                "%(acl)s" % (entry))
        return flask.Response(
            '\n'.join(output),
            content_type="text/plain;charset=UTF-8"
        )


@API.route('/groups/')
@API.route('/groups')
def api_groups():
    '''
    List group maintainer
    ---------------------
    Return the list FAS groups which have ACLs on one or more packages.

    ::

        /api/groups

    :kwarg format: Specify if the output if text or json.

    '''

    out_format = flask.request.args.get('format', 'text')

    if out_format not in ('text', 'json'):
        out_format = 'text'

    if request_wants_json():
        out_format = 'json'

    output = {}

    groups = pkgdblib.get_groups(SESSION)

    if out_format == 'json':
        output = {"groups": groups}
        output['total_groups'] = len(groups)
        return flask.jsonify(output)
    else:
        output = [
            "# Number of groups: %s" % len(groups)]
        for entry in sorted(groups):
            output.append("%s" % (entry))
        return flask.Response(
            '\n'.join(output),
            content_type="text/plain;charset=UTF-8"
        )


@API.route('/monitored/')
@API.route('/monitored')
def api_monitored():
    '''
    List packages monitored
    -----------------------
    Return the list of packages in pkgdb that have been flagged to be
    monitored by `anitya <http://release-monitoring.org>`_.

    ::

        /api/monitored

    :kwarg format: Specify if the output is text or json (default: text).

    '''

    out_format = flask.request.args.get('format', 'text')

    if out_format not in ('text', 'json'):
        out_format = 'text'

    if request_wants_json():
        out_format = 'json'

    output = {}

    pkgs = pkgdblib.get_monitored_package(SESSION)

    if out_format == 'json':
        output = {"packages": [pkg.name for pkg in pkgs]}
        output['total_packages'] = len(pkgs)
        return flask.jsonify(output)
    else:
        output = [
            "# Number of packages: %s" % len(pkgs)]
        for pkg in pkgs:
            output.append("%s" % (pkg.name))
        return flask.Response(
            '\n'.join(output),
            content_type="text/plain;charset=UTF-8"
        )


@API.route('/koschei/')
@API.route('/koschei')
def api_koschei():
    '''
    List packages monitored by koschei
    ----------------------------------
    Return the list of packages in pkgdb that have been flagged to be
    monitored by `koschei <https://apps.fedoraproject.org/koschei>`_.

    ::

        /api/koschei

    :kwarg format: Specify if the output is text or json (default: text).

    '''

    out_format = flask.request.args.get('format', 'text')

    if out_format not in ('text', 'json'):
        out_format = 'text'

    if request_wants_json():
        out_format = 'json'

    output = {}

    pkgs = pkgdblib.get_koschei_monitored_package(SESSION)

    if out_format == 'json':
        output = {"packages": [pkg.name for pkg in pkgs]}
        output['total_packages'] = len(pkgs)
        return flask.jsonify(output)
    else:
        output = [
            "# Number of packages: %s" % len(pkgs)]
        for pkg in pkgs:
            output.append("%s" % (pkg.name))
        return flask.Response(
            '\n'.join(output),
            content_type="text/plain;charset=UTF-8"
        )


@API.route('/dead/package/<pkg_name>/<clt_name>')
def api_dead_package(pkg_name, clt_name):
    '''
    Returned the content of the of dead.package file
    -----------------------
    Retired packages should have in their git a ``dead.package`` file
    containing the explanation as why the package was retired.
    This method calls cgit to return that explanation.

    ::

        /api/dead/package/acheck/master

    '''
    req = requests.get(
        'http://pkgs.fedoraproject.org/cgit/%s.git/plain/'
        'dead.package?h=%s' % (pkg_name, clt_name)
    )

    return flask.Response(
        req.text,
        content_type="text/plain;charset=UTF-8",
        status=req.status_code,
    )


@API.route('/retired/')
@API.route('/retired')
def api_retired():
    '''
    List packages retired
    ---------------------
    Return the list of packages in pkgdb that have been retired on all
    Fedora or EPEL collections.

    ::

        /api/retired

    :kwarg collection: Either `Fedora` or `Fedora EPEL` or any other
        collection name (default: Fedora)
    :kwarg format: Specify if the output is text or json (default: text).

    '''

    collection = flask.request.args.get('collection', 'Fedora')
    out_format = flask.request.args.get('format', 'text')

    if out_format not in ('text', 'json'):
        out_format = 'text'

    if request_wants_json():
        out_format = 'json'

    output = {}

    pkgs = pkgdblib.get_retired_packages(SESSION, collection=collection)

    if out_format == 'json':
        output = {
            "packages": [pkg.name for pkg in pkgs],
            "total_packages": len(pkgs),
            "collection": collection,
        }
        return flask.jsonify(output)
    else:
        output = [
            "# Number of packages: %s" % len(pkgs),
            "# collection: %s" % collection]
        for pkg in pkgs:
            output.append("%s" % (pkg.name))
        return flask.Response(
            '\n'.join(output),
            content_type="text/plain;charset=UTF-8"
        )
