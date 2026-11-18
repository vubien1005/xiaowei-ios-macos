/**
 * 正在执行的任务
 * {
 *   [onlySerial]: options
 * }
 */
const taskIdDataMap = {}

function timer (id, data, onlySerial, fn, op) {
    if (!Array.isArray(data)) return console.error('data is not array', data)
    if (data.length === 0) {
        fn({
            id,
            status: 'success',
            row: undefined
        })
        return
    }

    if (!taskIdDataMap[onlySerial]) return
    

    const row = data.shift()

    const start = performance.now()
    setTimeout(() => {
        if (!taskIdDataMap[onlySerial]) return
        
        const actualDelay = performance.now() - start
        fn({
            id,
            row: row,
            status: 'running',
            actualDelay
        })

        timer(...arguments)
    }, row.delay - 0.1)
}

self.onmessage = e => {
    const { id, type, data, onlySerial } = e.data

    if (!onlySerial) throw new Error('onlySerial is required')
    if (!type) throw new Error('type is required')
    if (!id) throw new Error('id is required')

    if (type === 'start') {
        taskIdDataMap[onlySerial] = e.data

        timer(id, data, onlySerial, (params) => {
            self.postMessage(params)
        })
    }
    else if (type === 'stop') {
        console.log('stop', onlySerial)
        delete taskIdDataMap[onlySerial]
    }
}
