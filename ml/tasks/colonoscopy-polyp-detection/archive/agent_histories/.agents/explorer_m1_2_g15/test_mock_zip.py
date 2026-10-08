import zipfile
import io
import pickle

def create_mock_weight_zip(dest_path):
    # Create a minimal valid PyTorch state_dict zip archive
    mock_state = {
        "decode_head.bias": ("tensor_mock", [1, 2, 3]),
        "backbone.weight": ("tensor_mock", [4, 5, 6])
    }
    pkl_bytes = pickle.dumps(mock_state, protocol=2)
    
    with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("archive/data.pkl", pkl_bytes)
        z.writestr("archive/byteorder", b"little")
        z.writestr("archive/.format_version", b"3")
        z.writestr("archive/data/0", b"\x00" * 64)
        z.writestr("archive/data/1", b"\x00" * 64)

def verify_mock_zip(path):
    assert zipfile.is_zipfile(path), "Not a zipfile"
    with zipfile.ZipFile(path) as z:
        test_res = z.testzip()
        assert test_res is None, f"testzip failed: {test_res}"
        print(f"Mock zip verified! Entries: {len(z.namelist())}")

if __name__ == "__main__":
    test_path = r"M:\chakramodel\.agents\explorer_m1_2_g15\mock_weights.zip"
    create_mock_weight_zip(test_path)
    verify_mock_zip(test_path)
