#
#
#

import re
import shlex
import time
from logging import getLogger
from uuid import uuid4

from google.cloud import dns
from google.cloud.dns import ManagedZone

from octodns.provider.base import BaseProvider
from octodns.record import Record

# TODO: remove __VERSION__ with the next major version release
__version__ = __VERSION__ = '1.0.0'


def add_trailing_dot(value):
    """
    Required function to handle cases where records being pushed
    to Google Cloud DNS do not end with a dot.

    :param value: Contains the record value
    :type  value: str

    :type return: str
    """
    if value[-1] != '.':
        value = f'{value}.'
    return value


def _batched_iterator(iterable, batch_size):
    n = len(iterable)
    for i in range(0, n, batch_size):
        yield iterable[i : min(i + batch_size, n)]


class GoogleCloudProvider(BaseProvider):
    SUPPORTS = set(
        (
            'A',
            'AAAA',
            'ALIAS',
            'CAA',
            'CNAME',
            'DS',
            'MX',
            'NAPTR',
            'NS',
            'PTR',
            'SPF',
            'SRV',
            'TXT',
        )
    )
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS_ROOT_NS = True

    CHANGE_LOOP_WAIT = 5

    def __init__(
        self,
        id,
        project=None,
        credentials_file=None,
        batch_size=1000,
        private=None,
        *args,
        **kwargs,
    ):
        if credentials_file:
            self.gcloud_client = dns.Client.from_service_account_json(
                credentials_file, project=project
            )
        else:
            self.gcloud_client = dns.Client(project=project)

        self.batch_size = batch_size

        self.private = private

        # Logger
        self.log = getLogger(f'GoogleCloudProvider[{id}]')
        self.id = id

        self._gcloud_zones = {}
        self._gcloud_zones_records = {}

        super().__init__(id, *args, **kwargs)

    def _apply(self, plan):
        """Required function of manager.py to actually apply a record change.

        :param plan: Contains the zones and changes to be made
        :type  plan: octodns.provider.base.Plan

        :type return: void
        """
        desired = plan.desired
        changes = plan.changes

        self.log.debug(
            '_apply: zone=%s, len(changes)=%d', desired.name, len(changes)
        )

        # Get gcloud zone, or create one if none existed before.
        if desired.name not in self.gcloud_zones:
            gcloud_zone = self._create_gcloud_zone(desired.name)
        else:
            gcloud_zone = self.gcloud_zones.get(desired.name)

        for batch in _batched_iterator(changes, self.batch_size):
            gcloud_changes = gcloud_zone.changes()

            for change in batch:
                class_name = change.__class__.__name__
                _rrset_func = getattr(self, f'_rrset_for_{change.record._type}')

                if class_name == 'Create':
                    gcloud_changes.add_record_set(
                        _rrset_func(gcloud_zone, change.record)
                    )

                elif class_name == 'Delete':
                    gcloud_changes.delete_record_set(
                        _rrset_func(
                            gcloud_zone,
                            change.existing,
                            gcloud_value=self._get_record_gcloud_value(
                                gcloud_zone, change.existing
                            ),
                        )
                    )

                elif class_name == 'Update':
                    gcloud_changes.delete_record_set(
                        _rrset_func(
                            gcloud_zone,
                            change.existing,
                            gcloud_value=self._get_record_gcloud_value(
                                gcloud_zone, change.existing
                            ),
                        )
                    )
                    gcloud_changes.add_record_set(
                        _rrset_func(gcloud_zone, change.new)
                    )

                else:
                    msg = (
                        f'Change type "{class_name}" for change '
                        f'"{str(change)}" is none of "Create", "Delete" '
                        'or "Update"'
                    )
                    raise RuntimeError(msg)

            gcloud_changes.create()

            for i in range(120):
                gcloud_changes.reload()
                # https://cloud.google.com/dns/api/v1/changes#resource
                # status can be one of either "pending" or "done"
                if gcloud_changes.status != 'pending':
                    break
                self.log.debug("Waiting for changes to complete")
                time.sleep(self.CHANGE_LOOP_WAIT)

            if gcloud_changes.status != 'done':
                timeout = i * self.CHANGE_LOOP_WAIT
                raise RuntimeError(f"Timeout reached after {timeout} seconds")

    def _create_gcloud_zone(self, dns_name):
        """Creates a google cloud ManagedZone with dns_name, and zone named
        derived from it. calls .create() method and returns it.

        :param dns_name: fqdn of zone to create
        :type  dns_name: str

        :type return: new google.cloud.dns.ManagedZone
        """
        # Zone name must begin with a letter, end with a letter or digit,
        # and only contain lowercase letters, digits or dashes,
        # and be 63 characters or less
        zone_name = f'zone-{dns_name.replace(".", "-")}-{uuid4().hex}'[:63]

        gcloud_zone = self.gcloud_client.zone(name=zone_name, dns_name=dns_name)
        gcloud_zone.create(client=self.gcloud_client)

        # add this new zone to the list of zones.
        self._gcloud_zones[gcloud_zone.dns_name] = gcloud_zone

        self.log.info(f"Created zone {zone_name}. Fqdn {dns_name}.")

        return gcloud_zone

    def _is_zone_private(self, zone: ManagedZone) -> bool:
        """Determine if a ManagedZone is private.
        :param zone: zone to check
        :type zone: google.cloud.dns.ManagedZone

        :return: True if the zone is private, False otherwise
        """
        return zone._properties.get('visibility', '') == 'private'

    def _filter_zone(self, zone: ManagedZone) -> bool:
        """Determine if the zone matches filtering criteria.

        :param zone: zone to check
        :type zone: google.cloud.dns.ManagedZone

        :return: True if the zone should be included, False otherwise
        """
        if self.private is None:
            return True
        return self.private is None or self.private == self._is_zone_private(
            zone
        )

    def _get_gcloud_zones(self, page_token=None):
        """
        Recursively fetches zones from Google Cloud DNS API and put the
        returned `ManagedZone` objects in cache.

        This function should not be called directly, please use
        `GoogleCloudProvider.gcloud_zones()` instead.

        :param page_token: Page token to get results from

        :return: void
        """

        gcloud_zones = self.gcloud_client.list_zones(page_token=page_token)
        for gcloud_zone in gcloud_zones:
            if self._filter_zone(gcloud_zone):
                self._gcloud_zones[gcloud_zone.dns_name] = gcloud_zone

        if gcloud_zones.next_page_token:
            self._get_gcloud_zones(gcloud_zones.next_page_token)

    def _get_gcloud_zone_records(self, gcloud_zone, page_token=None):
        """
        Recursively fetches zone records from Google Cloud DNS API and put the
        returned `ResourceRecordSet` objects in cache.

        This function should not be called directly, please use
        `GoogleCloudProvider.gcloud_zone_records()` instead.

        :param gcloud_zone: Zone to get records from
        :type gcloud_zone: google.cloud.dns.ManagedZone
        :param page_token: Page token to get results from

        :return: A resource record set
        :type return: list of google.cloud.dns.ResourceRecordSet
        """

        if not self._gcloud_zones_records.get(gcloud_zone.dns_name):
            self._gcloud_zones_records[gcloud_zone.dns_name] = []

        iterator = gcloud_zone.list_resource_record_sets(page_token=page_token)
        self._gcloud_zones_records[gcloud_zone.dns_name].extend(iterator)

        # There's more results.
        if iterator.next_page_token:
            self._get_gcloud_zone_records(
                gcloud_zone, page_token=iterator.next_page_token
            )

        return self._gcloud_zones_records[gcloud_zone.dns_name]

    def _get_record_gcloud_value(self, gcloud_zone, existing_record):
        fqdn = existing_record.fqdn
        _type = existing_record._type

        try:
            return next(
                r.rrdatas
                for r in self.gcloud_zone_records(gcloud_zone)
                if r.name == fqdn and r.record_type == _type
            )
        except StopIteration:
            pass

    @property
    def gcloud_zones(self):
        """
        Returns Google Cloud DNS zones list from cache or build zones cache
        if missing.

        :return: A dict of zones names as key and corresponding object as value
        :type return: dict of str: google.cloud.dns.ManagedZone
        """

        if not self._gcloud_zones:
            self._get_gcloud_zones()

        return self._gcloud_zones

    def gcloud_zone_records(self, gcloud_zone):
        """
        Returns a Google Cloud DNS zone records list from cache or build records
        cache if missing.

        :param gcloud_zone: Zone to get records from
        :type gcloud_zone: google.cloud.dns.ManagedZone

        :return: A resource record set
        :type return: list of google.cloud.dns.ResourceRecordSet
        """

        if not self._gcloud_zones_records.get(gcloud_zone.dns_name):
            self._get_gcloud_zone_records(gcloud_zone)

        return self._gcloud_zones_records[gcloud_zone.dns_name]

    def populate(self, zone, target=False, lenient=False):
        """Required function of manager.py to collect records from zone.

        :param zone: A dns zone
        :type  zone: octodns.zone.Zone
        :param target: Unused.
        :type  target: bool
        :param lenient: Unused. Check octodns.manager for usage.
        :type  lenient: bool

        :type return: void
        """

        self.log.debug(
            'populate: name=%s, target=%s, lenient=%s',
            zone.name,
            target,
            lenient,
        )

        exists = False
        before = len(zone.records)

        gcloud_zone = self.gcloud_zones.get(zone.name)

        if gcloud_zone:
            exists = True
            for gcloud_record in self.gcloud_zone_records(gcloud_zone):
                if gcloud_record.record_type not in self.SUPPORTS:
                    continue

                record_name = gcloud_record.name
                if record_name.endswith(zone.name):
                    # google cloud always return fqdn. Make relative record
                    # here. "root" records will then get the '' record_name,
                    # which is also the way octodns likes it.
                    record_name = record_name[: -(len(zone.name) + 1)]
                typ = gcloud_record.record_type
                data = getattr(self, f'_data_for_{typ}')
                data = data(gcloud_record)
                data['type'] = typ
                data['ttl'] = gcloud_record.ttl
                self.log.debug(
                    'populate: adding record %s records: %s', record_name, data
                )
                record = Record.new(zone, record_name, data, source=self)
                zone.add_record(record, lenient=lenient)

        self.log.info(
            'populate: found %s records, exists=%s',
            len(zone.records) - before,
            exists,
        )
        return exists

    def _data_for_A(self, gcloud_record):
        return {'values': gcloud_record.rrdatas}

    _data_for_AAAA = _data_for_A

    def _data_for_CAA(self, gcloud_record):
        return {
            'values': [
                {'flags': v[0], 'tag': v[1], 'value': v[2]}
                for v in [shlex.split(g) for g in gcloud_record.rrdatas]
            ]
        }

    def _data_for_CNAME(self, gcloud_record):
        return {'value': gcloud_record.rrdatas[0]}

    def _data_for_DS(self, gcloud_record):
        return {
            'values': [
                {
                    'key_tag': v[0],
                    'algorithm': v[1],
                    'digest_type': v[2],
                    'digest': v[3],
                }
                for v in [shlex.split(g) for g in gcloud_record.rrdatas]
            ]
        }

    def _data_for_MX(self, gcloud_record):
        return {
            'values': [
                {"preference": v[0], "exchange": v[1]}
                for v in [shlex.split(g) for g in gcloud_record.rrdatas]
            ]
        }

    def _data_for_NAPTR(self, gcloud_record):
        return {
            'values': [
                {
                    'order': v[0],
                    'preference': v[1],
                    'flags': v[2],
                    'service': v[3],
                    'regexp': v[4],
                    'replacement': v[5],
                }
                for v in [shlex.split(g) for g in gcloud_record.rrdatas]
            ]
        }

    _data_for_NS = _data_for_A

    _data_for_ALIAS = _data_for_CNAME

    _data_for_PTR = _data_for_CNAME

    _fix_semicolons = re.compile(r'(?<!\\);')

    def _data_for_SPF(self, gcloud_record):
        if len(gcloud_record.rrdatas) > 1:
            return {
                'values': [
                    self._fix_semicolons.sub('\\;', rr)
                    for rr in gcloud_record.rrdatas
                ]
            }
        return {
            'value': self._fix_semicolons.sub('\\;', gcloud_record.rrdatas[0])
        }

    def _data_for_SRV(self, gcloud_record):
        return {
            'values': [
                {'priority': v[0], 'weight': v[1], 'port': v[2], 'target': v[3]}
                for v in [shlex.split(g) for g in gcloud_record.rrdatas]
            ]
        }

    _data_for_TXT = _data_for_SPF

    def _rrset_for_A(self, gcloud_zone, record, gcloud_value=None):
        return gcloud_zone.resource_record_set(
            record.fqdn, record._type, record.ttl, gcloud_value or record.values
        )

    _rrset_for_AAAA = _rrset_for_A

    def _rrset_for_CAA(self, gcloud_zone, record, gcloud_value=None):
        return gcloud_zone.resource_record_set(
            record.fqdn,
            record._type,
            record.ttl,
            gcloud_value
            or [f'{v.flags} {v.tag} {v.value}' for v in record.values],
        )

    def _rrset_for_CNAME(self, gcloud_zone, record, gcloud_value=None):
        value = add_trailing_dot(record.value)
        return gcloud_zone.resource_record_set(
            record.fqdn, record._type, record.ttl, [value]
        )

    def _rrset_for_DS(self, gcloud_zone, record, gcloud_value=None):
        return gcloud_zone.resource_record_set(
            record.fqdn,
            record._type,
            record.ttl,
            gcloud_value
            or [
                f'{v.key_tag} {v.algorithm} {v.digest_type} {v.digest}'
                for v in record.values
            ],
        )

    def _rrset_for_MX(self, gcloud_zone, record, gcloud_value=None):
        return gcloud_zone.resource_record_set(
            record.fqdn,
            record._type,
            record.ttl,
            gcloud_value
            or [
                f'{v.preference} {add_trailing_dot(v.exchange)}'
                for v in record.values
            ],
        )

    def _rrset_for_NAPTR(self, gcloud_zone, record, gcloud_value=None):
        return gcloud_zone.resource_record_set(
            record.fqdn,
            record._type,
            record.ttl,
            gcloud_value
            or [
                f'{v.order} {v.preference} "{v.flags}" "{v.service}" '
                f'"{v.regexp}" {v.replacement}'
                for v in record.values
            ],
        )

    _rrset_for_NS = _rrset_for_A

    _rrset_for_ALIAS = _rrset_for_CNAME

    _rrset_for_PTR = _rrset_for_CNAME

    def _rrset_for_SPF(self, gcloud_zone, record, gcloud_value=None):
        return gcloud_zone.resource_record_set(
            record.fqdn,
            record._type,
            record.ttl,
            gcloud_value or record.chunked_values,
        )

    def _rrset_for_SRV(self, gcloud_zone, record, gcloud_value=None):
        return gcloud_zone.resource_record_set(
            record.fqdn,
            record._type,
            record.ttl,
            gcloud_value
            or [
                f'{v.priority} {v.weight} {v.port} {v.target}'
                for v in record.values
            ],
        )

    _rrset_for_TXT = _rrset_for_SPF
