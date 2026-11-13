# auto_copier

Desktop folder ကို reverse-name password နဲ့ zip လုပ်ပြီး destination သို့ ကူးတဲ့ Ubuntu app။

## Run from source

```bash
python3 auto_copier.py
```

`zip` မရှိရင် `sudo apt install zip` လုပ်ပါ။

## Binary

Ubuntu 22.04 မှာသာ install / remove လုပ်ပါ။

```bash
./build_binary.sh
./install_auto_copier
./remove_auto_copier
```

`build_binary.sh` က `dist/auto_copier` ကို ဆောက်ပြီး install ကို ခေါ်သည်။ `install_auto_copier` က binary ကို `~/.local/bin/auto_copier` မှာ တင်ပြီး Desktop နှင့် app menu မှာ icon တည်ဆောက်သည်။ `remove_auto_copier` က တပ်ဆင်ထားသော binary၊ Desktop icon၊ menu entry နှင့် icon ဖိုင်များကို ဖျက်သည်။ Project ထဲက `dist/auto_copier` ကို မဖျက်ပါ။

