export function createFrameScheduler(n){let e=null;return()=>{e===null&&(e=window.requestAnimationFrame(()=>{e=null,n()}))}}
