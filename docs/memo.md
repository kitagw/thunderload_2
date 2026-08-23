# git clone
git clone https://github.com/kitagw/thunderload_2

# git ユーザ設定
git config user.name "kitagw"
git config user.email "tomohisa.kitagawa@hotmail.com"

# 仮想環境用意
python3.11 -m venv .venv
source .venv/bin/activate

# pip
pip install --upgrade pip
pip install --upgrade Cython python-for-android buildozer 
pip install -r requirements.txt

# Buildozer
rm -rf .buildozer/android/platform/build-arm64-v8a/build/venv
buildozer -v android debug
