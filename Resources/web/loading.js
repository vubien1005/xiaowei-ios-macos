// 向页面添加 加载效果

document.body.classList.add('pageBeforeLoaded')
const style = document.createElement('style')
style.classList.add('pageBeforeLoadedStyle')
const dark = localStorage.getItem('dark') || null
style.innerHTML = `.pageBeforeLoaded {background-color: ${dark === 'true' ? '#272828' : '#ebeef1'};}`
document.head.appendChild(style)

window.unmountedPageBeforeLoaded = () => {
    document.body.classList.remove('pageBeforeLoaded')
    const style = document.querySelector('.pageBeforeLoadedStyle')
    if (style) style.remove()
}
