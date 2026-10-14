import cv2, numpy as np
W,H=1080,1920
rng=np.random.default_rng(7)
def rgb(r,g,b): return np.array([b,g,r],np.float32)
def grad(top,bot):
    t=np.linspace(0,1,H,dtype=np.float32)[:,None,None]
    return (top*(1-t)+bot*t)*np.ones((H,W,3),np.float32)
def light(img,cx,cy,r,gain):
    yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
    m=np.exp(-(((xx-cx)/r)**2+((yy-cy)/r)**2))[...,None]
    return img*(1+gain*m)
def vignette(img,k=0.22):
    yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
    d=np.sqrt(((xx-W/2)/(W*0.75))**2+((yy-H*0.4)/(H*0.7))**2)
    return img*(1-k*np.clip(d,0,1.4)**2)[...,None]
def blur_layer(img,mask,sigma):  # 描いたものをぼかして重ねる
    return img
LAY=np.zeros((H,W,3),np.float32); MSK=np.zeros((H,W),np.float32)
def draw_leaf(canvas,cx,cy,ln,wd,ang,col):
    tmp=np.zeros((H,W),np.uint8)
    cv2.ellipse(tmp,(int(cx),int(cy)),(int(ln),int(wd)),ang,0,360,255,-1,cv2.LINE_AA)
    m=tmp.astype(np.float32)/255
    # 葉の中で明暗をつける（上が明るい）
    shade=1.0+0.25*np.clip((cy-np.mgrid[0:H,0:1][0])/max(wd,1),-1,1)
    for c in range(3):
        LAY[...,c]=LAY[...,c]*(1-m)+m*col[c]
    MSK[:]=np.maximum(MSK,m)
def flush(img,sigma=11):
    global LAY,MSK
    Lb=cv2.GaussianBlur(LAY*MSK[...,None],(0,0),sigma); Mb=cv2.GaussianBlur(MSK,(0,0),sigma)
    out=img*(1-Mb[...,None])+Lb
    LAY=np.zeros((H,W,3),np.float32); MSK=np.zeros((H,W),np.float32); return out
def plant(canvas,cx,cy,scale=1.0,n=26,seed=1,base=(78,118,86)):
    r=np.random.default_rng(seed)
    for _ in range(n):
        ang=r.uniform(-80,80)-90
        L=r.uniform(120,230)*scale; Wd=r.uniform(26,46)*scale
        ox=r.uniform(-60,60)*scale; oy=r.uniform(-40,40)*scale
        k=r.uniform(0.75,1.2); col=tuple(int(min(255,c*k)) for c in base[::-1])
        a=np.deg2rad(ang)
        draw_leaf(canvas,cx+ox+np.cos(a)*L*0.8,cy+oy+np.sin(a)*L*0.8,L,Wd,ang,col)
def finish(img,sigma_blur,noise=2.0,vig=0.2):
    img=cv2.GaussianBlur(img,(0,0),sigma_blur)
    img=vignette(img,vig)
    img+=rng.normal(0,noise,img.shape).astype(np.float32)
    return np.clip(img,0,255).astype(np.uint8)

def A():  # 白壁＋観葉植物
    img=grad(rgb(236,234,229),rgb(222,220,215)); img=light(img,W*0.8,H*0.12,700,0.07)
    plant(img,170,H*0.40,1.25,30,3)
    cv2.rectangle(img,(70,int(H*0.40)+120),(270,int(H*0.40)+360),(205,208,212),-1)   # 鉢
    img=flush(img,12); return finish(img,5)
def B():  # 窓のブラインド
    img=grad(rgb(232,231,227),rgb(220,219,214))
    x0,y0,x1,y1=int(W*0.52),0,W,int(H*0.43)
    cv2.rectangle(img,(x0,y0),(x1,y1),(252,252,248),-1)
    for y in range(y0+14,y1,34): cv2.rectangle(img,(x0,y),(x1,y+19),(228,230,232),-1)   # スラット
    cv2.rectangle(img,(x0,y0),(x1,y1),(246,246,246),14)   # 窓枠
    plant(img,int(W*0.62),int(y1)+10,0.85,16,5,(82,124,88))
    img=flush(img,11); return finish(img,5)
def C():  # 木の棚
    img=grad(rgb(238,235,228),rgb(226,222,214))
    y=int(H*0.30)
    cv2.rectangle(img,(0,y),(int(W*0.55),y+26),(88,128,178),-1)   # 板(BGR 木目色)
    cols=[(60,90,150),(180,160,120),(90,150,120),(140,110,90),(200,190,170)]
    x=30
    for i,c in enumerate(cols*2):
        w=int(rng.integers(34,60)); h=int(rng.integers(120,210))
        if x+w>W*0.38: break
        cv2.rectangle(img,(x,y-h),(x+w,y),c,-1); x+=w+int(rng.integers(4,10))
    cv2.rectangle(img,(int(W*0.40),y-70),(int(W*0.52),y),(215,215,218),-1)
    plant(img,int(W*0.46),y-30,0.7,14,9,(80,120,86))
    img=flush(img,9); return finish(img,6)
def D():  # パーテーション＋緑のアクセント
    img=grad(rgb(228,230,232),rgb(214,217,220))
    panels=[(0,int(W*0.30),(226,228,231)),(int(W*0.30),int(W*0.70),(218,221,225)),(int(W*0.70),W,(118,152,126))]
    for a,b,c in panels:
        cv2.rectangle(img,(a,0),(b,int(H*0.52)),c[::-1] if c[2]<150 else c,-1)
    for a,b,_ in panels: cv2.line(img,(a,0),(a,int(H*0.52)),(200,203,206),6)
    cv2.rectangle(img,(0,int(H*0.52)),(W,H),(212,214,217),-1)
    return finish(img,5)
def E():  # 額縁
    img=grad(rgb(240,237,231),rgb(229,225,218))
    for (x0,y0,x1,y1,c) in [(90,260,330,560,(120,150,170)),(380,260,520,420,(150,175,140))]:
        cv2.rectangle(img,(x0-14,y0-14),(x1+14,y1+14),(250,250,250),-1)
        cv2.rectangle(img,(x0,y0),(x1,y1),c,-1)
        cv2.circle(img,((x0+x1)//2,(y0+y1)//2+20),int((x1-x0)*0.22),(200,205,210),-1)
    plant(img,int(W*0.88),int(H*0.42),1.0,22,12)
    cv2.rectangle(img,(int(W*0.80),int(H*0.42)+100),(int(W*0.97),int(H*0.42)+300),(205,208,212),-1)
    img=flush(img,12); return finish(img,5)
for k,f in zip('ABCDE',[A,B,C,D,E]):
    cv2.imwrite(f'/Users/hayato.kobayashi/second-brain-repo/video-ad-studio/projects/nakamura-cr01/assets/bg_office/bg_{k}.png',f())
print('ok')
