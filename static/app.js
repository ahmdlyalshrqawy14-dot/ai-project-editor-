const $=id=>document.getElementById(id);
let cur='';

// Tabs
document.querySelectorAll('.tab').forEach(t=>{
  t.onclick=()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
    document.querySelectorAll('.panel').forEach(x=>x.classList.remove('on'));
    t.classList.add('on');
    $('t-'+t.dataset.t).classList.add('on');
  };
});

// Upload
const dz=$('dz'),fi=$('fi');
dz.ondragover=e=>{e.preventDefault();dz.style.borderColor='#6366f1'};
dz.ondragleave=()=>dz.style.borderColor='';
dz.ondrop=e=>{e.preventDefault();dz.style.borderColor='';
  if(e.dataTransfer.files[0])up(e.dataTransfer.files[0])};
fi.onchange=e=>{if(e.target.files[0])up(e.target.files[0])};

async function up(f){
  const fd=new FormData();fd.append('file',f);
  st('us','⏳ جاري الرفع...','');
  try{
    const r=await fetch('/api/upload',{method:'POST',body:fd});
    const d=await r.json();
    if(d.status==='ok'){
      st('us',`✅ ${d.name} - ${d.count} ملف`,'ok');
      lf();document.querySelector('[data-t="files"]').click();
    }else st('us','❌ '+d.error,'er');
  }catch(e){st('us','❌ '+e.message,'er')}
}

async function lf(){
  const d=await(await fetch('/api/files')).json();
  $('fc').textContent=d.total;
  $('ft').innerHTML='';$('efl').innerHTML='';
  $('tf').innerHTML='<option value="">كل المشروع</option>';
  d.files.forEach(f=>{
    const i=document.createElement('div');i.className='fi';
    i.innerHTML='📄 '+f;i.onclick=()=>of(f);$('ft').appendChild(i);
    const e=i.cloneNode(true);e.onclick=()=>of(f);$('efl').appendChild(e);
    const o=document.createElement('option');o.value=f;o.textContent=f;
    $('tf').appendChild(o);
  });
}

async function of(p){
  const d=await(await fetch('/api/file/'+encodeURIComponent(p))).json();
  cur=p;$('efn').textContent=p;$('ce').value=d.content;
  document.querySelector('[data-t="editor"]').click();
}

async function sav(){
  if(!cur)return;
  await fetch('/api/file/'+encodeURIComponent(cur),{method:'PUT',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({content:$('ce').value})});
  alert('✅ تم الحفظ');
}

// AI Chat
async function snd(){
  const msg=$('ci').value.trim();if(!msg)return;
  const tf=$('tf').value||null,md=$('am').value;
  am(msg,'u');$('ci').value='';am('⏳ ...','a','th');
  try{
    const d=await(await fetch('/api/chat',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:msg,target_file:tf,mode:md})})).json();
    rmth();
    if(d.status==='ok'){
      am(d.response,'a');
      if(d.applied&&d.applied.length){am('✅ تم تعديل: '+d.applied.join(', '),'a');lf()}
    }else am('❌ '+d.error,'a');
  }catch(e){rmth();am('❌ '+e.message,'a')}
}

async function bk(){
  const ins=prompt('اكتب تعليمات التعديل الشامل:');if(!ins)return;
  am('🚀 '+ins,'u');am('⏳ جاري المعالجة...','a','th');
  try{
    const d=await(await fetch('/api/chat/bulk',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({instruction:ins})})).json();
    rmth();
    if(d.status==='ok'){am(d.response,'a');
      if(d.applied&&d.applied.length){am('✅ '+d.applied.length+' ملف','a');lf()}
    }else am('❌ '+d.error,'a');
  }catch(e){rmth();am('❌ '+e.message,'a')}
}

function am(t,c,id){
  const d=document.createElement('div');d.className='m '+c;
  if(id)d.id=id;d.textContent=t;$('cm').appendChild(d);
  $('cm').scrollTop=$('cm').scrollHeight;
}
function rmth(){const e=$('th');if(e)e.remove()}

// Settings
async function ss(){
  const d={
    google_key:$('gk').value, google_model:$('gm').value,
    deepseek_key:$('dk').value, deepseek_model:$('dm').value,
    qwen_key:$('qk').value, qwen_model:$('qm').value,
    active_provider:$('ap').value
  };
  await fetch('/api/settings',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
  st('ss','✅ تم الحفظ','ok');
}

// Export / Reset
async function exp(){
  const r=await fetch('/api/export',{method:'POST'});
  const b=await r.blob();const u=URL.createObjectURL(b);
  const a=document.createElement('a');a.href=u;
  a.download='project_modified.zip';a.click();URL.revokeObjectURL(u);
}
async function rst(){
  if(!confirm('متأكد؟'))return;
  await fetch('/api/reset',{method:'POST'});location.reload();
}

function st(id,msg,cls){
  const e=$(id);e.textContent=msg;
  e.className='st'+(cls?' '+cls:'');
}

$('ci').addEventListener('keydown',e=>{
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();snd()}
});
