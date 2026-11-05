# -*- coding: utf-8 -*-
"""给 DefaultEditor 注入结构化表单面板"""
import io, sys

path = 'use-session-keep-alive-D8zQp1gm.js'
data = io.open(path, encoding='utf-8').read()

# ---- 新增的 setup 顶层代码（sf ref + 拼接/解析函数 + syncT）----
SETUP_CODE = (
    'let sf=J({brief:``,info:``,experience:``,reference:``}),syncT=()=>{};'
    'function buildRaw(){var c=g.value?.getHTML()||``;'
    'function esc(s){return String(s==null?``:s).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`)}'
    'function blk(s){s=String(s==null?``:s).trim();if(!s)return``;'
    'return s.split(/\\n+/).map(function(x){return `<p>${esc(x)}</p>`}).join(``)}'
    'var f=sf.value,o=``;'
    'o+=`<h2>作品说明</h2>`+blk(f.brief);'
    'o+=`<h2>作品内容</h2>`+c;'
    'o+=`<h2>项目信息</h2>`+blk(f.info);'
    'o+=`<h2>体验方式</h2>`+blk(f.experience);'
    'o+=`<h2>参考资料</h2>`+blk(f.reference);'
    'return o}'
    'function parseFields(raw){var s=raw||``,f={brief:``,content:``,info:``,experience:``,reference:``};'
    'function h2(name){var m=s.match(new RegExp(`<h2[^>]*>\\\\s*`+name+`\\\\s*</h2>`,`i`));return m?m.index:-1}'
    'function eof(from){if(from<0)return-1;var st=s.indexOf(`</h2>`,from);return st<0?-1:st+5}'
    'function tt(h){return String(h||``).replace(/<br\\s*\\/?>/gi,`\\n`).replace(/<\\/(p|li|h[1-6]|div|blockquote)>/gi,`\\n`).replace(/<[^>]+>/g,``).replace(/&lt;/g,`<`).replace(/&gt;/g,`>`).replace(/&amp;/g,`&`).replace(/&quot;/g,`"`).replace(/&#39;/g,`\'`).replace(/\\n{3,}/g,`\\n\\n`).trim()}'
    'function slice(from,to){if(from<0)return``;var a=eof(from);if(a<0)return``;var b=to>=0?to:s.length;return s.slice(a,b).trim()}'
    'var a=h2(`作品说明`),b=h2(`作品内容`),b2=h2(`技术方案与实现`),c=h2(`项目信息`),d=h2(`体验方式`),e=h2(`参考资料`);'
    'if(b<0)b=b2;'
    'if(a>=0){f.brief=tt(slice(a,b));f.content=slice(b,c);f.info=tt(slice(c,d));f.experience=tt(slice(d,e));f.reference=tt(slice(e,-1))}'
    'else{f.content=s}'
    'return f}'
)

# ---- onUpdate 拼接 + editor 初始 content 解析 ----
ONUPDATE_OLD = 'let t=kt(()=>{let e=g.value?.getHTML()+``;o(`update:raw`,e),o(`update:content`,e),o(`update`,e)},250);g.value=new Ot({content:i.raw,'
ONUPDATE_NEW = (
    'let f=parseFields(i.raw);sf.value={brief:f.brief,info:f.info,experience:f.experience,reference:f.reference};'
    'let t=kt(()=>{let r=buildRaw();o(`update:raw`,r),o(`update:content`,r),o(`update`,r)},250);syncT=t;'
    'g.value=new Ot({content:f.content,'
)

# ---- raw watch 解析回填 ----
WATCH_OLD = 'It(()=>i.raw,()=>{i.raw!==g.value?.getHTML()&&g.value?.commands.setContent(i.raw)},{immediate:!0});'
WATCH_NEW = (
    'It(()=>i.raw,()=>{let f=parseFields(i.raw);'
    'if(f.content===g.value?.getHTML()&&f.brief===sf.value.brief&&f.info===sf.value.info&&f.experience===sf.value.experience&&f.reference===sf.value.reference)return;'
    'sf.value={brief:f.brief,info:f.info,experience:f.experience,reference:f.reference};'
    'if(f.content!==g.value?.getHTML())g.value?.commands.setContent(f.content)},{immediate:!0});'
)

# ---- 表单面板节点 ----
FORM_OLD = 'onKeydown:ge(w,[`enter`])},null,40,ke),_e(n.$slots,`content`)'

def ta(key, rows, label, ph):
    # 一个带 label 的 textarea 字段
    return (
        'I(`div`,null,['
        'I(`label`,{class:`mb-1 block text-xs font-medium text-gray-700`},' + repr(label) + '),'
        'I(`textarea`,{value:sf.value.' + key + ',rows:' + str(rows) + ',placeholder:' + repr(ph)
        + ',class:`w-full resize-y rounded-md border border-gray-200 bg-white p-2 text-sm leading-relaxed text-gray-900 placeholder:text-gray-400 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-100`,'
        + 'onInput:e=>{sf.value.' + key + '=e.target.value;syncT()}},null,40,[`value`])'
        '])'
    )

form_node = (
    'I(`div`,{class:`mb-4 rounded-xl border border-blue-100 bg-blue-50/40 p-4`},['
    'I(`div`,{class:`mb-3 flex items-center justify-between`},['
    'I(`span`,{class:`text-sm font-semibold text-blue-700`},`结构化信息`),'
    'I(`span`,{class:`text-xs text-gray-500`},`按固定字段填写，保存后自动排版为统一结构`)'
    ']),'
    'I(`div`,{class:`space-y-3`},['
    + ta('brief', 2, '作品说明', '一句话介绍作品功能与亮点（将显示为卡片简介）') + ','
    + ta('info', 4, '项目信息', '技术栈 / 负责人 / 团队 / 项目链接等，每行一条') + ','
    + ta('experience', 3, '体验方式', '访问地址 / 演示账号 / 操作步骤等') + ','
    + ta('reference', 3, '参考资料', '来源链接 / 文献等，每行一条') + ','
    'I(`div`,{class:`rounded-md bg-white/70 px-3 py-2 text-xs text-gray-500`},`「作品内容」请在下方正文编辑区填写，保存时自动置于作品说明与项目信息之间。`)'
    '])'
    '])'
)

FORM_NEW = FORM_OLD.replace('_e(n.$slots,`content`)', form_node + ',_e(n.$slots,`content`)')

# ---- 执行替换 ----
cnt = 0
for old, new in [
    ('y=J(!1);function ae(e){', 'y=J(!1);' + SETUP_CODE + 'function ae(e){'),
    (ONUPDATE_OLD, ONUPDATE_NEW),
    (WATCH_OLD, WATCH_NEW),
    (FORM_OLD, FORM_NEW),
]:
    if data.count(old) != 1:
        print('锚点匹配数异常:', data.count(old), '->', old[:50])
        sys.exit(1)
    data = data.replace(old, new)
    cnt += 1

io.open(path, 'w', encoding='utf-8').write(data)
print('完成，共替换', cnt, '处')
print('新文件长度:', len(data))
