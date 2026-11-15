export function cacheElements(t,n=document){return Object.fromEntries(t.map(e=>[e,n.getElementById(e)]))}
