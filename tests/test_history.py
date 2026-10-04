from datetime import date, datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from ute.history.normalize import normalize_quarters, TZ, ACTIVE_LABEL
from ute.history.store import IntervalStore
from ute.history.publish import publish_history


def payload(points):
    return {"CURVA_DE_CONSUMO": {"data_array": [{"label": ACTIVE_LABEL, "data": points}]}}


class NormalizationTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 10, 1)
        self.stamp = datetime(2026, 10, 1, tzinfo=TZ).timestamp() * 1000
        self.now = datetime(2026, 10, 2, tzinfo=timezone.utc)

    def normalize(self, points):
        return normalize_quarters(payload(points), self.day, self.day, self.now)

    def test_timezone_zero_and_missing(self):
        self.assertEqual(self.normalize([[self.stamp, .1], [self.stamp+900000, None],
                                         [self.stamp+1800000, 0]]), {
            "2026-10-01T03:00:00+00:00": .1, "2026-10-01T03:30:00+00:00": 0.0})

    def test_reject_invalid_readings_and_conflicts(self):
        for points in ([[self.stamp, -1]], [[self.stamp, True]],
                       [[self.stamp, float('nan')]], [[self.stamp+1000, .1]],
                       [[self.stamp, .1], [self.stamp, .2]], [[self.stamp-900000, .1]]):
            with self.subTest(points=points), self.assertRaises(ValueError):
                self.normalize(points)

    def test_partial_interval_and_year_boundary(self):
        stamp = datetime(2025, 12, 31, 23, 45, tzinfo=TZ).timestamp()*1000
        now = datetime.fromtimestamp(stamp/1000+300, timezone.utc)
        self.assertEqual(normalize_quarters(payload([[stamp, .1]]), date(2025, 12, 31),
                                           date(2026, 1, 1), now), {})

    def test_missing_or_multiple_series(self):
        for series in ([], [{"label": ACTIVE_LABEL, "data": []}]*2):
            with self.assertRaises(ValueError):
                normalize_quarters({"CURVA_DE_CONSUMO": {"data_array": series}},
                                   self.day, self.day, self.now)


class StoreTests(unittest.TestCase):
    def test_restart_revision_idempotence_and_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder)/'history.sqlite3')
            store = IntervalStore(path, 'a')
            store.merge({'2026-10-01T03:00:00+00:00': .1})
            store.merge({'2026-10-01T03:00:00+00:00': .2})
            self.assertEqual(IntervalStore(path, 'a').read(), {'2026-10-01T03:00:00+00:00': .2})
            self.assertEqual(IntervalStore(path, 'b').read(), {})


class PublishTests(unittest.TestCase):
    def test_chunks_latest_and_acknowledgements(self):
        publisher = MagicMock(topic_prefix='UTE', discovery_prefix='homeassistant')
        publisher.client.publish.return_value.rc = 0
        publisher.client.publish.return_value.is_published.return_value = True
        values = {'2026-10-01T03:00:00+00:00': .1, '2026-10-02T03:00:00+00:00': .2}
        publish_history(publisher, 'service', values)
        calls = publisher.client.publish.call_args_list
        self.assertEqual(len(calls), 5)
        self.assertIn('UTC', calls[-2].args[1])
        self.assertIn('measurement', calls[-1].args[1])
        for call in calls:
            self.assertEqual(call.kwargs, {'qos': 1, 'retain': True})
        self.assertEqual(publisher.client.publish.return_value.wait_for_publish.call_count, 5)

    def test_empty_does_not_publish_and_failure_is_reported(self):
        publisher = MagicMock()
        publish_history(publisher, 'service', {})
        publisher.client.publish.assert_not_called()
        publisher.client.publish.return_value.rc = 1
        with self.assertRaises(RuntimeError):
            publish_history(publisher, 'service', {'2026-10-01T03:00:00+00:00': .1})


class PortalTests(unittest.TestCase):
    def test_thirty_day_batches_and_quarter_hour_request(self):
        from ute.history.portal import fetch
        with patch('ute.history.portal.requests.Session') as factory:
            session = factory.return_value.__enter__.return_value
            session.post.return_value.text = 'authenticated'
            session.get.return_value.json.return_value = payload([])
            self.assertEqual(fetch({'document': 'test', 'password': 'test'},
                {'serviceAgreementId': 'sa', 'servicePointId': 'sp'},
                date(2026, 1, 1), date(2026, 2, 1)), {})
            calls = [call for call in session.get.call_args_list if call.args[0].endswith('cmgraficar')]
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0].kwargs['params']['graficas[0][parms][agrupacion]'], 'QH')
            self.assertEqual(calls[1].kwargs['params']['graficas[0][parms][fechaInicial]'], '31-01-2026')

    def test_failed_login(self):
        from ute.history.portal import fetch
        with patch('ute.history.portal.requests.Session') as factory:
            factory.return_value.__enter__.return_value.post.return_value.text = '<input name="password">'
            with self.assertRaises(ValueError):
                fetch({'document': 'test', 'password': 'test'}, {}, date(2026, 1, 1), date(2026, 1, 1))


class SynchronizationTests(unittest.TestCase):
    def test_saved_before_mqtt_failure_and_replayed_on_retry(self):
        import history_main
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {
            'UTE_SERVICE_ID': 'sa', 'UTE_SERVICE_POINT_ID': 'sp',
            'MQTT_BROKER': 'test', 'UTE_HISTORY_DB': str(Path(folder)/'history.sqlite3'),
        }), patch.object(history_main, 'CredentialsManager') as manager, \
                patch.object(history_main, 'fetch') as fetcher, \
                patch.object(history_main, 'MQTTPublisher') as publisher, \
                patch.object(history_main, 'publish_history') as publish:
            manager.return_value.get_user_credentials.return_value = {
                'username': 'test', 'password': 'test'}
            values = {'2026-10-01T03:00:00+00:00': .1}
            fetcher.return_value = values
            publisher.return_value.connect.return_value = False
            with self.assertRaises(RuntimeError):
                history_main.synchronize(date(2026, 10, 1), date(2026, 10, 1))
            publisher.return_value.disconnect.assert_called_once()
            publisher.return_value.connect.return_value = True
            fetcher.return_value = {}
            history_main.synchronize(date(2026, 10, 1), date(2026, 10, 1))
            publish.assert_called_once_with(publisher.return_value, 'sa', values)


if __name__ == '__main__':
    unittest.main()
