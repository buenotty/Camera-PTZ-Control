import unittest
from src.core.visca_client import VISCAClient

class TestVISCAClient(unittest.TestCase):
    def setUp(self):
        self.client = VISCAClient("192.0.2.1", 52381)

    def test_value_to_nibbles(self):
        # 0x1234 -> 0x01, 0x02, 0x03, 0x04
        nibbles = self.client._value_to_nibbles(0x1234, 4)
        self.assertEqual(nibbles, bytes([0x01, 0x02, 0x03, 0x04]))

    def test_nibbles_to_value(self):
        val = self.client._nibbles_to_value(bytes([0x01, 0x02, 0x03, 0x04]))
        self.assertEqual(val, 0x1234)

    def test_header_generation(self):
        payload = bytes([0x81, 0x01, 0x06, 0x01, 0x08, 0x08, 0x03, 0x03, 0xFF]) # Stop
        header = self.client._create_header(payload, is_inquiry=False)
        self.assertEqual(len(header), 8)
        self.assertEqual(header[0:2], b'\x01\x00') # Command type
        self.assertEqual(int.from_bytes(header[2:4], 'big'), len(payload))

    def test_direction_bytes(self):
        # Verify right, left, up, down mapping
        self.assertEqual(self.client._get_direction_bytes("Left"), (0x01, 0x03))
        self.assertEqual(self.client._get_direction_bytes("Right"), (0x02, 0x03))
        self.assertEqual(self.client._get_direction_bytes("Up"), (0x03, 0x01))
        self.assertEqual(self.client._get_direction_bytes("Down"), (0x03, 0x02))
        self.assertEqual(self.client._get_direction_bytes("Stop"), (0x03, 0x03))

if __name__ == '__main__':
    unittest.main()
