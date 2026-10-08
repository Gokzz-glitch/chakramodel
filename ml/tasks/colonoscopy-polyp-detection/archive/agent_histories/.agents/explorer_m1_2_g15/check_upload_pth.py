import zipfile
import io

with zipfile.ZipFile(r"C:\Users\imgk3\Downloads\om-finalkaggle-upload") as outer:
    pth_bytes = outer.read("weights/chakra_transformer_best.pth")
    with zipfile.ZipFile(io.BytesIO(pth_bytes)) as inner:
        infos = inner.infolist()
        print(f"Inner zip entries: {len(infos)}")
        pkls = [i.filename for i in infos if i.filename.endswith(".pkl")]
        print(f"Pickle files: {pkls}")
        print(f"Total uncompressed size: {sum(i.file_size for i in infos):,} bytes")
