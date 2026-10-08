import os
import zipfile

zips = [
    r"C:\Users\imgk3\Downloads\om-finalkaggle-upload",
    r"J:\My Drive\downloads\chakra_transformer_best.zip",
    r"J:\My Drive\downloads\finalmuruga-harae.zip",
    r"J:\My Drive\downloads\resultscomaprision successful.zip",
    r"J:\My Drive\downloads\combocldoutput7-8.zip",
    r"J:\My Drive\downloads\crossvali (1)result.zip",
    r"J:\My Drive\downloads\anti_fabrication_toolkit_v6_hardened.zip",
    r"J:\My Drive\downloads\CHAKRAMODEL_OM_4\anti_fabrication_toolkit.zip",
    r"J:\My Drive\downloads\CHAKRAMODEL_OM_4\anti_fabrication_toolkit_cloud_ready.zip",
    r"J:\My Drive\downloads\CHAKRAMODEL_OM_4\ChakraModel_Kaggle_Code.zip",
    r"J:\My Drive\downloads\CHAKRAMODEL_OM_4\ChakraModel_Kaggle_Verification.zip",
    r"J:\My Drive\downloads\CHAKRAMODEL_OM_4\chakramodel_weights_PRIVATE.zip",
]

for zp in zips:
    print(f"\n==========================================")
    print(f"Archive: {zp}")
    if not os.path.exists(zp):
        print("  DOES NOT EXIST")
        continue
    try:
        is_zip = zipfile.is_zipfile(zp)
        print(f"  is_zipfile: {is_zip}, size: {os.path.getsize(zp):,}")
        if is_zip:
            with zipfile.ZipFile(zp) as z:
                names = z.namelist()
                print(f"  Total items: {len(names)}")
                for n in names[:15]:
                    print(f"    {n}")
                if len(names) > 15:
                    print(f"    ... and {len(names)-15} more items")
        else:
            with open(zp, 'rb') as f:
                head = f.read(32)
                print(f"  Header hex: {head.hex()}")
    except Exception as e:
        print(f"  ERROR: {e}")
