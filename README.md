# auto_copier

Desktop folder ကို header-encrypted 7z လုပ်ပြီး destination သို့ ကူးတဲ့ Ubuntu app။ Default password ကို ရွေးထားရင် ဖိုင်အမည်ပြောင်းပြန်ဖြစ်ပြီး၊ ဖြုတ်ထားရင် space မပါသော password ကို တောင်းသည်။ Archive Manager က password မထည့်ရင် ဖိုင်စာရင်းကို မပြပါ။

## Run from source

```bash
python3 auto_copier.py
```

`7z` မရှိရင် `sudo apt install p7zip-full` လုပ်ပါ။ Source က git directory ဖြစ်ရင် `.gitignore` ပါ file နဲ့ directory များကို archive ထဲမထည့်ပါ။

## Binary

Ubuntu 22.04 မှာသာ install / remove လုပ်ပါ။

```bash
./build_binary.sh
./install_auto_copier
./remove_auto_copier
```

`build_binary.sh` က `dist/auto_copier` ကို ဆောက်ပြီး install ကို ခေါ်သည်။ `install_auto_copier` က binary ကို `~/.local/bin/auto_copier` မှာ တင်ပြီး Desktop နှင့် app menu မှာ icon တည်ဆောက်သည်။ `remove_auto_copier` က တပ်ဆင်ထားသော binary၊ Desktop icon၊ menu entry နှင့် icon ဖိုင်များကို ဖျက်ပြီး Desktop Icons ကို refresh လုပ်သည်။ Project ထဲက `dist/auto_copier` ကို မဖျက်ပါ။

