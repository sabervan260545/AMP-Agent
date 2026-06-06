# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

import os

print("🔍 [Environment Check]")
print(f"Current Working Directory: {os.getcwd()}")

# 检查我们预期的路径是否存在
target_dir = "/app/models/hemopi2/model/Data"
print(f"Checking Target Dir: {target_dir}")

if os.path.exists(target_dir):
    print("✅ Directory exists!")
    print("📂 Files inside:")
    for f in os.listdir(target_dir):
        print(f"   - {f}")
else:
    print("❌ Directory NOT FOUND!")
    print("📂 Listing /app/models to debug:")
    try:
        for root, dirs, files in os.walk("/app/models"):
            print(f"   {root}/")
            for d in dirs: print(f"     [{d}]")
    except Exception as e:
        print(f"Error walking: {e}")
