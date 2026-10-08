import json
import os

with open("M:\\chakramodel\\verify_kaggle.py", "r") as f:
    verify_script = f.read()
    
with open("M:\\chakramodel\\anti_fabrication\\anti_fabrication_toolkit\\core\\harness_core.py", "r") as f:
    harness_script = f.read()

notebook = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# ChakraModel V6 Strict Verification - True Anti-Fabrication Harness\n",
    "\n",
    "This notebook securely writes BOTH `verify_kaggle.py` and `harness_core.py` directly to the disk, avoiding the need to upload the Anti-Fabrication Toolkit separately!\n",
    "\n",
    "**Before running:**\n",
    "1. Make sure you have added your Image Dataset, Code Dataset, and Weights Dataset.\n",
    "2. Ensure you run this using **Save Version -> Save & Run All (Commit)**."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!pip install -q ultralytics timm opencv-python-headless pycocotools"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "import os\n",
    "import sys\n",
    "import shutil\n",
    "import glob\n",
    "import json\n",
    "import re\n",
    "\n",
    "###################################################################\n",
    "# CONFIGURATION\n",
    "###################################################################\n",
    "\n",
    "# 1. Update THIS path to the exact subfolder (Make sure images/ and masks/ are directly inside it!)\n",
    "DATASET_ROOT = '/kaggle/input/polypdb-polyp-raw/PolypDB/PolypDB/PolypDB_center_wise/Center_1'\n",
    "\n",
    "# 2. Update THIS name so your CSV and Verification Card are labeled correctly\n",
    "VERIFY_DATASET_NAME = \"PolypDB_Center_1\"\n",
    "\n",
    "WORKING_DATASET = '/kaggle/working/dataset_copy'\n",
    "\n",
    "if os.path.exists(WORKING_DATASET):\n",
    "    shutil.rmtree(WORKING_DATASET)\n",
    "shutil.copytree(DATASET_ROOT, WORKING_DATASET)\n",
    "print(f\"Dataset securely copied to {WORKING_DATASET}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "%%writefile /kaggle/working/harness_core.py\n"
   ] + [line + "\n" for line in harness_script.split("\n")]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "%%writefile /kaggle/working/verify_kaggle.py\n"
   ] + [line + "\n" for line in verify_script.split("\n")]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "sys.path.insert(0, '/kaggle/working')\n",
    "\n",
    "from harness_core import plant_multi_canary, run_live, verify, sign_verdict\n",
    "\n",
    "print(\"Planting canaries...\")\n",
    "secret = plant_multi_canary(WORKING_DATASET)\n",
    "\n",
    "extra_env = {\n",
    "    \"VERIFY_NONCE\": secret[\"nonce\"],\n",
    "    \"VERIFY_DATASET_NAME\": VERIFY_DATASET_NAME,\n",
    "    \"VERIFY_DATASET_ROOT\": WORKING_DATASET\n",
    "}\n",
    "\n",
    "print(f\"\\nRunning verification for {VERIFY_DATASET_NAME}...\")\n",
    "stdout_text, arrivals, elapsed, retcode = run_live('/kaggle/working/verify_kaggle.py', extra_env, timeout_sec=10000)\n",
    "\n",
    "print(stdout_text)\n",
    "\n",
    "if retcode != 0:\n",
    "    print(f\"FATAL: verify_kaggle.py exited with code {retcode}\")\n",
    "else:\n",
    "    # Parse claimed total from stdout\n",
    "    match = re.search(r\"Total Evaluated Images:\\s*(\\d+)\", stdout_text)\n",
    "    claimed_total = int(match.group(1)) if match else -1\n",
    "    \n",
    "    # Use harness core to verify output logic\n",
    "    real_count = len(os.listdir(os.path.join(WORKING_DATASET, \"images\")))\n",
    "    verdict_dict = verify(stdout_text, arrivals, elapsed, secret, claimed_total, real_count)\n",
    "    \n",
    "    card = {\n",
    "        \"project\": \"ChakraModel\",\n",
    "        \"dataset\": VERIFY_DATASET_NAME,\n",
    "        \"nonce\": secret[\"nonce\"],\n",
    "        \"decision\": \"ADMITTED\" if verdict_dict[\"pass\"] else \"WITHHELD\",\n",
    "        \"findings\": verdict_dict[\"findings\"],\n",
    "        \"elapsed_sec\": verdict_dict[\"elapsed_sec\"]\n",
    "    }\n",
    "    \n",
    "    signed_card = sign_verdict(card, secret[\"hmac_key\"])\n",
    "    \n",
    "    with open('/kaggle/working/completion_card.json', 'w') as f:\n",
    "        json.dump(signed_card, f, indent=2)\n",
    "        \n",
    "    print(f\"\\n=========================================\")\n",
    "    print(f\"VERDICT: {card['decision']}\")\n",
    "    for finding in card['findings']:\n",
    "        print(f\"  - {finding}\")\n",
    "    print(f\"Saved to completion_card.json\")\n",
    "    print(f\"=========================================\")\n"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.10.12"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}

with open('M:\\chakramodel\\kaggle_wrapper_v6.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)
