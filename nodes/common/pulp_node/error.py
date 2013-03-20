# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.


class NodeError(Exception):

    def __init__(self, error_id, **details):
        self.error_id = error_id
        self.details = details

    def load(self, _dict):
        if isinstance(_dict, dict):
            self.__dict__.update(_dict)
        else:
            raise ValueError(_dict)

    def dict(self):
        return self.__dict__

    def __eq__(self, other):
        return self.error_id == other.error_id and self.details == other.details


class SummaryError(NodeError):

    def __init__(self, error_id, **details):
        super(SummaryError, self).__init__(error_id, **details)
        self.count = 1


class CaughtException(NodeError):

    ERROR_ID = 'exception'

    def __init__(self, exception, repo_id=None):
        super(CaughtException, self).__init__(
            self.ERROR_ID, message=str(exception), repo_id=repo_id)


class PurgeOrphansError(NodeError):

    ERROR_ID = 'rest.child.orphans.purge'

    def __init__(self, http_code):
        super(PurgeOrphansError, self).__init__(self.ERROR_ID, http_code=http_code)


class RepoSyncRestError(NodeError):

    ERROR_ID = 'rest.child.repository.synchronization'

    def __init__(self, repo_id, http_code):
        super(RepoSyncRestError, self).__init__(self.ERROR_ID, repo_id=repo_id, http_code=http_code)


class GetBindingsError(NodeError):

    ERROR_ID = 'rest.parent.bindings.get'

    def __init__(self, http_code):
        super(GetBindingsError, self).__init__(self.ERROR_ID, http_code=http_code)


class GetChildUnitsError(NodeError):

    ERROR_ID = 'rest.child.units.get'

    def __init__(self, repo_id):
        super(GetChildUnitsError, self).__init__(self.ERROR_ID, repo_id=repo_id)


class GetParentUnitsError(NodeError):

    ERROR_ID = 'rest.parent.units.get'

    def __init__(self, repo_id):
        super(GetParentUnitsError, self).__init__(self.ERROR_ID, repo_id=repo_id)


class ImporterNotInstalled(NodeError):

    ERROR_ID = 'plugins.child.importer.missing'

    def __init__(self, repo_id, type_id):
        super(ImporterNotInstalled, self).__init__(self.ERROR_ID, repo_id=repo_id, type_id=type_id)


class DistributorNotInstalled(NodeError):

    ERROR_ID = 'plugins.child.distributor.missing'

    def __init__(self, repo_id, type_id):
        super(DistributorNotInstalled, self).__init__(self.ERROR_ID, repo_id=repo_id, type_id=type_id)


class ManifestDownloadError(NodeError):

    ERROR_ID = 'download.parent.manifest'

    def __init__(self, url):
        super(ManifestDownloadError, self).__init__(self.ERROR_ID, url=url)


class UnitDownloadError(SummaryError):

    ERROR_ID = 'download.parent.manifest.units'

    def __init__(self):
        super(UnitDownloadError, self).__init__(self.ERROR_ID)


class AddUnitError(SummaryError):

    ERROR_ID = 'child.unit.add'

    def __init__(self):
        super(AddUnitError, self).__init__(self.ERROR_ID)


class DeleteUnitError(SummaryError):

    ERROR_ID = 'child.unit.delete'

    def __init__(self):
        super(DeleteUnitError, self).__init__(self.ERROR_ID)


class ErrorList(list):

    def append(self, error):
        """
        Append the error.
          - Duplicates ignored.
          - Increment the 'count' on Summary Errors.
        :param error: An error to append.
        :type error: NodeError
        """
        if not isinstance(error, NodeError):
            raise ValueError(error)
        if isinstance(error, SummaryError):
            for e in self:
                if e == error:
                    e.count += 1
                    return
        if error not in self:
            super(ErrorList, self).append(error)

    def extend(self, iterable):
        """
        Extend the list using append().
        :param iterable: An iterable containing errors.
        :type iterable: iterable
        """
        for e in iterable:
            self.append(e)

    def update(self, **details):
        """
        Update the details of all contained errors.
        :param details: A details dictionary.
        :type details: dict
        """
        for e in self:
            e.details.update(details)
