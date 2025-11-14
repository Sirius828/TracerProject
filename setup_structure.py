import os

# 创建目录结构
directories = [
    "models",
    "windows",
    "dialogs"
]

for directory in directories:
    os.makedirs(directory, exist_ok=True)
    # 创建__init__.py文件
    with open(os.path.join(directory, "__init__.py"), "w") as f:
        f.write("# 自动生成的__init__.py文件\n")
