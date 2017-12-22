import unittest
from os import path
from tempfile import TemporaryDirectory

from helperFunctions.config import get_config_for_testing
from helperFunctions.fileSystem import get_test_data_dir
from helperFunctions.file_tree import FileTreeNode
from storage.MongoMgr import MongoMgr
from storage.db_interface_backend import BackEndDbInterface
from storage.db_interface_frontend import FrontEndDbInterface
from test.common_helper import create_test_firmware, create_test_file_object

TESTS_DIR = get_test_data_dir()
test_file_one = path.join(TESTS_DIR, 'get_files_test/testfile1')
TMP_DIR = TemporaryDirectory(prefix='fact_test_')


class TestStorageDbInterfaceFrontend(unittest.TestCase):

    def setUp(self):
        self._config = get_config_for_testing(TMP_DIR)
        self.mongo_server = MongoMgr(config=self._config)
        self.db_frontend_interface = FrontEndDbInterface(config=self._config)
        self.db_backend_interface = BackEndDbInterface(config=self._config)
        self.test_firmware = create_test_firmware()

    def tearDown(self):
        self.db_backend_interface.client.drop_database(self._config.get('data_storage', 'main_database'))
        self.db_frontend_interface.shutdown()
        self.db_backend_interface.shutdown()
        self.mongo_server.shutdown()

    def test_get_meta_list(self):
        self.db_backend_interface.add_firmware(self.test_firmware)
        list_of_firmwares = self.db_frontend_interface.get_meta_list()
        test_output = list_of_firmwares.pop()
        self.assertEqual(test_output[1], 'test_vendor test_router - 0.1 (Router)', 'Firmware not successfully received')

    def test_get_hid_firmware(self):
        self.db_backend_interface.add_firmware(self.test_firmware)
        result = self.db_frontend_interface.get_hid(self.test_firmware.get_uid())
        self.assertEqual(result, 'test_vendor test_router - 0.1 (Router)', 'fw hid not correct')

    def test_get_hid_fo(self):
        test_fo = create_test_file_object(bin_path='get_files_test/testfile2')
        test_fo.virtual_file_path = {'a': ['|a|/test_file'], 'b': ['|b|/get_files_test/testfile2']}
        self.db_backend_interface.add_file_object(test_fo)
        result = self.db_frontend_interface.get_hid(test_fo.get_uid(), root_uid='b')
        self.assertEqual(result, '/get_files_test/testfile2', 'fo hid not correct')
        result = self.db_frontend_interface.get_hid(test_fo.get_uid())
        self.assertIsInstance(result, str, 'result is not a string')
        self.assertEqual(result[0], '/', 'first character not correct if no root_uid set')
        result = self.db_frontend_interface.get_hid(test_fo.get_uid(), root_uid='c')
        self.assertEqual(result[0], '/', 'first character not correct if invalid root_uid set')

    def test_get_file_name(self):
        self.db_backend_interface.add_firmware(self.test_firmware)
        result = self.db_frontend_interface.get_file_name(self.test_firmware.get_uid())
        self.assertEqual(result, 'test.zip', 'name not correct')

    def test_get_hid_invalid_uid(self):
        result = self.db_frontend_interface.get_hid('foo')
        self.assertEqual(result, '', 'invalid uid should result in empty string')

    def test_get_firmware_attribute_list(self):
        self.db_backend_interface.add_firmware(self.test_firmware)
        self.assertEqual(self.db_frontend_interface.get_device_class_list(), ['Router'])
        self.assertEqual(self.db_frontend_interface.get_vendor_list(), ['test_vendor'])
        self.assertEqual(self.db_frontend_interface.get_firmware_attribute_list('device_name', {'vendor': 'test_vendor', 'device_class': 'Router'}), ['test_router'])
        self.assertEqual(self.db_frontend_interface.get_firmware_attribute_list('version'), ['0.1'])
        self.assertEqual(self.db_frontend_interface.get_device_name_dict(), {'Router': {'test_vendor': ['test_router']}})

    def test_get_data_for_nice_list(self):
        uid_list = [self.test_firmware.get_uid()]
        self.db_backend_interface.add_firmware(self.test_firmware)
        nice_list_data = self.db_frontend_interface.get_data_for_nice_list(uid_list, uid_list[0])
        self.assertEquals(sorted(['size', 'virtual_file_paths', 'uid', 'mime-type', 'files_included']), sorted(nice_list_data[0].keys()))
        self.assertEqual(nice_list_data[0]['uid'], self.test_firmware.get_uid())

    def test_generic_search(self):
        self.db_backend_interface.add_firmware(self.test_firmware)
        # str input
        result = self.db_frontend_interface.generic_search('{"file_name": "test.zip"}')
        self.assertEqual(result, [self.test_firmware.get_uid()], 'Firmware not successfully received')
        # dict input
        result = self.db_frontend_interface.generic_search({'file_name': 'test.zip'})
        self.assertEqual(result, [self.test_firmware.get_uid()], 'Firmware not successfully received')

    def test_all_uids_found_in_database(self):
        self.db_backend_interface.client.drop_database(self._config.get('data_storage', 'main_database'))
        uid_list = [self.test_firmware.get_uid()]
        self.assertFalse(self.db_frontend_interface.all_uids_found_in_database(uid_list))
        self.db_backend_interface.add_firmware(self.test_firmware)
        self.assertTrue(self.db_frontend_interface.all_uids_found_in_database([self.test_firmware.get_uid()]))

    def test_get_number_of_firmwares_in_db(self):
        self.assertEqual(self.db_frontend_interface.get_number_of_firmwares_in_db(), 0)
        self.db_backend_interface.add_firmware(self.test_firmware)
        self.assertEqual(self.db_frontend_interface.get_number_of_firmwares_in_db(), 1)

    def test_get_x_last_added_firmwares(self):
        self.assertEqual(self.db_frontend_interface.get_last_added_firmwares(), [], 'empty db should result in empty list')
        test_fw_one = create_test_firmware(device_name='fw_one')
        self.db_backend_interface.add_firmware(test_fw_one)
        test_fw_two = create_test_firmware(device_name='fw_two', bin_path='container/test.7z')
        self.db_backend_interface.add_firmware(test_fw_two)
        test_fw_three = create_test_firmware(device_name='fw_three', bin_path='container/test.cab')
        self.db_backend_interface.add_firmware(test_fw_three)
        result = self.db_frontend_interface.get_last_added_firmwares(limit_x=2)
        self.assertEqual(len(result), 2, 'Number of results should be 2')
        self.assertEqual(result[0]['device_name'], 'fw_three', 'last firmware is not first entry')
        self.assertEqual(result[1]['device_name'], 'fw_two', 'second last firmware is not the second entry')

    def test_generate_file_tree_node(self):
        parent_fw = create_test_firmware()
        child_fo = create_test_file_object()
        child_fo.processed_analysis['file_type'] = {'mime': 'sometype'}
        uid = parent_fw.get_uid()
        child_fo.virtual_file_path = {uid: ['|{}|/folder/{}'.format(uid, child_fo.file_name)]}
        parent_fw.files_included = {child_fo.get_uid()}
        self.db_backend_interface.add_object(parent_fw)
        self.db_backend_interface.add_object(child_fo)
        for node in self.db_frontend_interface.generate_file_tree_node(uid, uid):
            self.assertIsInstance(node, FileTreeNode)
            self.assertEqual(node.name, parent_fw.file_name)
            self.assertTrue(node.has_children)
        for node in self.db_frontend_interface.generate_file_tree_node(child_fo.get_uid(), uid):
            self.assertIsInstance(node, FileTreeNode)
            self.assertEqual(node.name, 'folder')
            self.assertTrue(node.has_children)
            virtual_grand_child = node.get_list_of_child_nodes()[0]
            self.assertEqual(virtual_grand_child.type, 'sometype')
            self.assertFalse(virtual_grand_child.has_children)
            self.assertEqual(virtual_grand_child.name, child_fo.file_name)

    def test_get_number_of_total_matches(self):
        parent_fw = create_test_firmware()
        child_fo = create_test_file_object()
        uid = parent_fw.get_uid()
        child_fo.virtual_file_path = {uid: ['|{}|/folder/{}'.format(uid, child_fo.file_name)]}
        self.db_backend_interface.add_object(parent_fw)
        self.db_backend_interface.add_object(child_fo)
        query = '{{"$or": [{{"_id": "{}"}}, {{"_id": "{}"}}]}}'.format(uid, child_fo.get_uid())
        self.assertEqual(self.db_frontend_interface.get_number_of_total_matches(query, only_parent_firmwares=False), 2)
        self.assertEqual(self.db_frontend_interface.get_number_of_total_matches(query, only_parent_firmwares=True), 1)

    def test_get_other_versions_of_firmware(self):
        parent_fw1 = create_test_firmware(version='1')
        self.db_backend_interface.add_object(parent_fw1)
        parent_fw2 = create_test_firmware(version='2', bin_path='container/test.7z')
        self.db_backend_interface.add_object(parent_fw2)
        parent_fw3 = create_test_firmware(version='3', bin_path='container/test.cab')
        self.db_backend_interface.add_object(parent_fw3)

        other_versions = self.db_frontend_interface.get_other_versions_of_firmware(parent_fw1)
        self.assertEqual(len(other_versions), 2, 'wrong number of other versions')
        self.assertIn({'_id': parent_fw2.get_uid(), 'version': '2'}, other_versions)
        self.assertIn({'_id': parent_fw3.get_uid(), 'version': '3'}, other_versions)

        other_versions = self.db_frontend_interface.get_other_versions_of_firmware(parent_fw2)
        self.assertIn({'_id': parent_fw3.get_uid(), 'version': '3'}, other_versions)
