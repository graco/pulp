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


from gettext import gettext as _
from logging import getLogger

from pulp_node import constants
from pulp_node.handlers.model import *
from pulp_node.handlers.validation import ChildValidator
from pulp_node.error import NodeError, CaughtException
from pulp_node.handlers.reports import StrategyReport, HandlerProgress, RepositoryReport


log = getLogger(__name__)


# --- i18n ------------------------------------------------------------------------------

STRATEGY_UNSUPPORTED = _('Handler strategy "%(s)s" not supported')


# --- abstract strategy -----------------------------------------------------------------


class HandlerStrategy(object):
    """
    Provides strategies for synchronizing repositories between pulp servers.
    :ivar cancelled: The flag indicating that the current operation
        has been cancelled.
    :type cancelled: bool
    :var progress: A progress report.
    :type progress: HandlerProgress
    :var report: The summary report.
    :type report: HandlerReport
    """

    def __init__(self, progress, report):
        """
        :param progress: A progress reporting object.
        :type progress: HandlerProgress
        :param report: A summary reporting object.
        :type report: StrategyReport
        """
        self.cancelled = False
        self.progress = progress
        self.report = report

    def synchronize(self, bindings, options):
        """
        Synchronize child repositories based on bindings.
        :param bindings: A list of consumer binding payloads.
        :type bindings: list
        :param options: synchronization options.
        :type options: dict
        :return: The synchronization report.
        """
        self.report.setup(bindings)
        self.progress.started(bindings)
        try:
            validator = ChildValidator(self.report)
            validator.validate(bindings)
            if self.report.failed():
                return
            self._synchronize(bindings, options)
            if options.get(constants.PURGE_ORPHANS_KEYWORD):
                ChildRepository.purge_orphans()
        except NodeError, ne:
            self.report.errors.append(ne)
        except Exception, e:
            log.exception('synchronization failed')
            error = CaughtException(e)
            self.report.errors.append(error)
        finally:
            self.progress.finished()

    def _synchronize(self, bindings, options):
        """
        Synchronize child repositories based on bindings.
        Must be overridden by subclasses.
        :param bindings: A list of consumer binding payloads.
        :type bindings: list
        :param options: synchronization options.
        :type options: dict
        :return: The synchronization report.
        """
        raise NotImplementedError()

    def cancel(self):
        """
        Cancel the current operation.
        """
        self.cancelled = True

    # --- protected ---------------------------------------------------------------------

    def _add_repositories(self, bindings):
        """
        Add or update repositories based on bindings.
          - Merge repositories found in BOTH parent and child.
          - Add repositories found in the parent but NOT in the child.
        :param bindings: List of bind payloads.
        :type bindings: list
        """
        for bind in bindings:
            if self.cancelled:
                break
            try:
                repo_id = bind['repo_id']
                details = bind['details']
                parent = Repository(repo_id, details)
                child = ChildRepository.fetch(repo_id)
                if child:
                    self.report[repo_id].action = RepositoryReport.MERGED
                    child.merge(parent)
                else:
                    child = ChildRepository(repo_id, parent.details)
                    self.report[repo_id].action = RepositoryReport.ADDED
                    child.add()
            except NodeError, ne:
                self.report.errors.append(ne)
            except Exception, e:
                log.exception(repo_id)
                error = CaughtException(e, repo_id)
                self.report.errors.append(error)

    def _synchronize_repositories(self, repo_ids, options):
        """
        Run synchronization on repositories.
        :param repo_ids: A list of repo IDs.
        :type repo_ids: list
        :param options: Unit update options.
        :type options: dict
        """
        for repo_id in repo_ids:
            if self.cancelled:
                break
            repo = ChildRepository(repo_id)
            try:
                progress = self.progress.find_report(repo_id)
                report = repo.run_synchronization(progress)
                progress.finished()
                details = report['details']
                for _dict in details['errors']:
                    e = NodeError(None)
                    e.load(_dict)
                    self.report.errors.append(e)
                _report = self.report[repo_id]
                _report.units.added = report['added_count']
                _report.units.updated = report['updated_count']
                _report.units.removed = report['removed_count']
            except NodeError, ne:
                self.report.errors.append(ne)
            except Exception, e:
                log.exception(repo_id)
                error = CaughtException(e, repo_id)
                self.report.errors.append(error)

    def _delete_repositories(self, bindings):
        """
        Delete repositories found in the child but NOT in the parent.
        :param bindings: List of bind payloads.
        :type bindings: list
        """
        parent = [b['repo_id'] for b in bindings]
        child = [r.repo_id for r in ChildRepository.fetch_all()]
        for repo_id in child:
            if self.cancelled:
                break
            try:
                if repo_id not in parent:
                    self.report[repo_id].action = RepositoryReport.DELETED
                    repo = ChildRepository(repo_id)
                    repo.delete()
            except NodeError, ne:
                self.report.errors.append(ne)
            except Exception, e:
                log.exception(repo_id)
                error = CaughtException(e, repo_id)
                self.report.errors.append(error)

    def _touched_repositories(self):
        """
        Get a list of repositories that have been added or updated.
        :return: A list of repository IDs.
        """
        dirty = []
        for report in self.report.repository.values():
            if report.action in (RepositoryReport.ADDED, RepositoryReport.MERGED):
                dirty.append(report.repo_id)
        return dirty


# --- strategies ------------------------------------------------------------------------


class Mirror(HandlerStrategy):

    def _synchronize(self, bindings, options):
        """
        Synchronize repositories.
          - Add/Merge bound repositories as needed.
          - Synchronize all bound repositories.
          - Purge unbound repositories.
          - Purge orphaned content units.
        :param bindings: A list of bind payloads.
        :type bindings: list
        :param options: Unit update options.
        :type options: dict
        """
        self._add_repositories(bindings)
        self._delete_repositories(bindings)
        self._synchronize_repositories(self._touched_repositories(), options)


class Additive(HandlerStrategy):

    def _synchronize(self, bindings, options):
        """
        Synchronize repositories.
          - Add/Merge bound repositories as needed.
          - Synchronize all bound repositories.
        :param bindings: A list of bind payloads.
        :type bindings: list
        :param options: Unit update options.
        :type options: dict
        """
        self._add_repositories(bindings)
        self._synchronize_repositories(self._touched_repositories(), options)


# --- factory ---------------------------------------------------------------------------


STRATEGIES = {
    constants.MIRROR_STRATEGY: Mirror,
    constants.ADDITIVE_STRATEGY: Additive,
}


class StrategyUnsupported(Exception):

    def __init__(self, name):
        msg = STRATEGY_UNSUPPORTED % {'s': name}
        Exception.__init__(self, msg)


def find_strategy(name):
    """
    Find a strategy (class) by name.
    :param name: A strategy name.
    :type name: str
    :return: A strategy class.
    :rtype: callable
    :raise: StrategyUnsupported on not found.
    """
    try:
        return STRATEGIES[name]
    except KeyError:
        raise StrategyUnsupported(name)