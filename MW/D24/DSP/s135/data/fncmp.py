import re,subprocess,sys,bisect
def symtab(elf):
    out=subprocess.run(['arm-none-eabi-nm','--print-size','-n',elf],capture_output=True,text=True).stdout
    syms=[]
    for ln in out.splitlines():
        p=ln.split()
        if len(p)==4: syms.append((int(p[0],16),int(p[1],16),p[3]))
        elif len(p)==3 and re.fullmatch(r'[0-9a-f]+',p[0]): syms.append((int(p[0],16),0,p[2]))
    return syms
def sym_for(syms,addr):
    for a,sz,n in syms:
        if a<=addr and (addr<a+sz or (sz==0 and addr==a)): return f'{n}+{addr-a}' if addr!=a else n
    return f'0x{addr:x}'
def dump(elf):
    syms=symtab(elf)
    out=subprocess.run(['arm-none-eabi-objdump','-d','--no-show-raw-insn',elf],capture_output=True,text=True).stdout
    fns={}; cur=None
    for ln in out.splitlines():
        m=re.match(r'^[0-9a-f]{8} <([^>]+)>:',ln)
        if m: cur=m.group(1); fns[cur]=[]; continue
        if cur is None or not ln.strip(): cur=None; continue
        m=re.match(r'^\s*([0-9a-f]+):\t(.*)$',ln)
        if not m: continue
        ins=m.group(2)
        ins=re.sub(r'\s*@.*$','',ins)                       # drop objdump comments
        # .word literals -> symbol names
        w=re.match(r'^\.word\s+0x([0-9a-f]+)$',ins.strip())
        if w: ins='.word '+sym_for(syms,int(w.group(1),16))
        # branch/call targets -> symbol names
        ins=re.sub(r'\b[0-9a-f]{4,8}\s+<([^>]+)>',r'<\1>',ins)
        fns[cur].append(' '.join(ins.split()))
    return fns
a=dump(sys.argv[1]); b=dump(sys.argv[2])
watch=['Poll','Eol','RdRadioSwitch','RdRadioSwitches','WrRadioLed','WrRadioLeds',
       'WrEncLed','WrEncLeds','TestEnc','TestMessage','Uart1_Int','main',
       'MX_GPIO_Init','SystemClock_Config','BlkOn','BlkOf','HlpOn','HlpOf','MfOn','MfOf','Test',
       'IgnOn','Tick','Meter','Spare','Error_Handler','UART1_Read','MX_TIM1_Init','MX_TIM3_Init',
       'MX_TIM15_Init','MX_ADC_Init','MX_USART1_UART_Init','HAL_TIM_MspPostInit']
bad=[]
for f in watch:
    if f not in a or f not in b: bad.append(f'{f}: MISSING'); continue
    if a[f]!=b[f]:
        d=[(x,y) for x,y in zip(a[f],b[f]) if x!=y]
        bad.append(f'{f}: DIFFERS, first={d[0] if d else "len"}')
print('\n'.join(bad) if bad else f'ALL {len(watch)} WATCHED FUNCTIONS INSTRUCTION-IDENTICAL (symbolised)')
# also: every function present in A, not just the watch list
allf=[f for f in a if f in b]
diffs=[f for f in allf if a[f]!=b[f]]
print(f'functions in both: {len(allf)}; differing: {len(diffs)} -> {sorted(diffs)}')
print(f'only in B: {sorted(set(b)-set(a))}')
print(f'only in A: {sorted(set(a)-set(b))}')
