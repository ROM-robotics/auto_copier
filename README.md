# auto_copier

Desktop folder ကို header-encrypted 7z လုပ်ပြီး destination သို့ ကူးတဲ့ Ubuntu app။ Default password ကို ရွေးထားရင် ဖိုင်အမည်ပြောင်းပြန်ဖြစ်ပြီး၊ ဖြုတ်ထားရင် space မပါသော password ကို တောင်းသည်။ Archive Manager က password မထည့်ရင် ဖိုင်စာရင်းကို မပြပါ။

Archive ဖိုင်အမည်ပုံစံမှာ `source-name_version_YYYYMMDD_HHMMSS.7z` ဖြစ်သည်။

## Run from source

```bash
python3 auto_copier.py
```

`7z` မရှိရင် `sudo apt install p7zip-full` လုပ်ပါ။ `.gitignore` စည်းမျဉ်းများကို ဖတ်ရန် `git` လည်းလိုအပ်သည်။ Source folder ထဲမှာ `.gitignore` ရှိရင် အဲဒီဖိုင်ရဲ့ rule တွေနဲ့ကိုက်ညီတဲ့ file နဲ့ directory များကို archive ထဲမထည့်ပါ။ Source folder အပေါ်ဘက် directory များရှိ `.gitignore` ကို မဖတ်ပါ။

## Binary

Ubuntu 22.04 မှာသာ install / remove လုပ်ပါ။

```bash
./build_binary.sh
./install_auto_copier
./remove_auto_copier
```

`build_binary.sh` က `dist/auto_copier` ကို ဆောက်ပြီး install ကို ခေါ်သည်။ `install_auto_copier` က binary ကို `~/.local/bin/auto_copier` မှာ တင်ပြီး Desktop နှင့် app menu မှာ icon တည်ဆောက်သည်။ `remove_auto_copier` က တပ်ဆင်ထားသော binary၊ Desktop icon၊ menu entry နှင့် icon ဖိုင်များကို ဖျက်ပြီး Desktop Icons ကို refresh လုပ်သည်။ Project ထဲက `dist/auto_copier` ကို မဖျက်ပါ။

