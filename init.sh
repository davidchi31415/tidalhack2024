rm a2s s2a
mkfifo a2s s2a

./stream -m ./models/ggml-tiny.en.bin -t 6 --step 0 --length 5000 -vth 0.6 > s2a < a2s &
python assistant.py < s2a > a2s