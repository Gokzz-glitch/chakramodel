import zipfile
import io

print("=== resultscomaprision successful.zip ===")
with zipfile.ZipFile(r"J:\My Drive\downloads\resultscomaprision successful.zip") as z:
    for info in z.infolist():
        print(f"{info.filename:70} {info.file_size:>12,d} bytes")

print("\n=== chakramodel_weights_PRIVATE.zip ===")
with zipfile.ZipFile(r"J:\My Drive\downloads\CHAKRAMODEL_OM_4\chakramodel_weights_PRIVATE.zip") as z:
    for info in z.infolist():
        print(f"{info.filename:50} {info.file_size:>14,d} bytes  {info.date_time}")
