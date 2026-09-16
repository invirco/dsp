CUR = [0,1,2,3,12,13,14,15, 4,5,6,7,16,17,18,19, 8,9,10,11,20,21,22,23]
ORDER = [1,13,2,14,3,15,4,16,5,17,6,18,7,19,8,20,9,21,10,22,11,23,12,24]  # app ChannelOrder = physical idx 1..24
POS_SLOT = {1:7,2:6,3:5,4:4,5:2,6:3,7:0,8:1}; POS_AIN = {1:8,2:7,3:6,4:5,5:3,6:4,7:1,8:2}
XLR = [('U15',0,list(range(15,23))),('U39',1,list(range(25,33))),('U60',2,list(range(35,43)))]
rows=[]; new=[None]*24
idx=0
for u,ad,js in XLR:
    for k,j in enumerate(js,1):
        idx+=1; ch=ORDER[idx-1]; slot=POS_SLOT[k]; i=8*ad+slot
        new[i]=ch-1
        p_now = 24-idx          # send position that reaches this register today
        rows.append((j,u,k,POS_AIN[k],slot,ad,i,CUR[i]+1,ch,idx,p_now,ORDER[p_now-1] if p_now>=1 else 'SHIFT'))
print('| XLR | ADC | pos | AIN | slot | AD lane | packed RX i | today lands on C1_IN | panel ch = proposed C1_IN | chain idx | today reached by send p (label) |')
print('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|')
for r in rows:
    print('| J%d | %s | %d | %d | %d | AD%d | %d | %02d | **%02d** | %d | %d (`%s`) |' % (r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],r[9],r[10], r[11] if r[11]=='SHIFT' else 'ch%d'%r[11]))
print(); print('proposed D24 patch AD0..AD2:', new[0:8], new[8:16], new[16:24])
print('check ch5 at', new.index(4), 'J25 packed', 8+7)
