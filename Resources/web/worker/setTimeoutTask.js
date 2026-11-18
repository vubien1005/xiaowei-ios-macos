/**
 * 正在执行的任务
 * {
 *   [onlySerial]: options
 * }
 */
const taskIdDataMap = {}

function timer(id, data, fn) {
    if (!Array.isArray(data)) return console.error('data is not array', data)
    if (data.length === 0) {
        fn({
            id,
            status: 'success',
            row: undefined
        })
        return
    }


    const row = data.shift()

    setTimeout(() => {
        fn({
            id,
            row: row,
            status: 'running',
        })

        timer(...arguments)
    }, row.delay - 0.1)
}

self.onmessage = e => {
    const { id, data, fn } = e.data

    if (!id) throw new Error('id is required')
    if (!Array.isArray(data)) throw new Error('data 需要数组类型')

    timer(id, data, (params) => {
        self.postMessage(params)
    })
}
