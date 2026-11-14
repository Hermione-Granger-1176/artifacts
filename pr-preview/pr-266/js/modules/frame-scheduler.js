export function createFrameScheduler(n,r){let e=null;return()=>{e===null&&(e=(r??window).requestAnimationFrame(()=>{e=null,n()}))}}
