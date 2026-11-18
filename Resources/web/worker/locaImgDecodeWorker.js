// 每设备独立存储最新帧（只保留 1 帧）
const queues = new Map()

// 解码器池（仅 ImageDecoder 用）
const decoders = new Map()

// -------------------------
// 1. 运行时只检查一次能力
// -------------------------
let decodeFrame

if (typeof ImageDecoder === 'function') {
  // --------------------------------------------
  // ✔ 使用 ImageDecoder（最快）
  // --------------------------------------------
  decodeFrame = async function (serial, buffer) {
    let decoder = decoders.get(serial)

    decoder = new ImageDecoder({
      data: buffer,
      type: 'image/jpeg',
    })

    // if (!decoder) {
    //   decoder = new ImageDecoder({
    //     data: buffer,
    //     type: 'image/jpeg',
    //   })
    //   decoders.set(serial, decoder)
    // }
    // else {
    //   decoder.configure({
    //     data: buffer,
    //     type: 'image/jpeg',
    //   })
    // }

    try {
      const result = await decoder.decode()
      // 注意：ImageDecoder 产出的是 VideoFrame（不是 ImageBitmap），
      // 它占用的是原生内存，必须由接收方显式 close()，否则只能等 GC 回收，
      // 控制台会刷 "A VideoFrame was garbage collected without being closed"
      return result.image
    }
    finally {
      // 每帧都新建一个解码器，用完立即释放，避免解码器资源堆到 GC 才回收。
      // 已经返回的帧不受影响，仍可正常绘制。
      decoder.close()
    }
  }
}
else {
  // --------------------------------------------
  // ✔ fallback：createImageBitmap（广兼容）
  // --------------------------------------------
  decodeFrame = async function (serial, buffer) {
    const blob = new Blob([buffer], { type: 'image/webp' })
    const bitmap = await createImageBitmap(blob)
    return bitmap
  }

  console.log('[worker] Using createImageBitmap (fallback)')
}

// -------------------------
// 2. WebSocket → Worker 通信
// -------------------------
onmessage = async (e) => {
  const { serial, base64 } = e.data

  let q = queues.get(serial)
  if (!q) {
    q = { frame: null, running: false }
    queues.set(serial, q)
  }

  // ★ 永远只保留最新 1 帧
  q.frame = base64

  if (q.running) return
  q.running = true

  // 解码循环：只处理最新帧
  while (q.frame) {
    const frame = q.frame
    q.frame = null

    let bitmap = null
    try {
      const buffer = base64ToBuffer(frame)

      // ★ 调用已经确定好的解码器
      bitmap = await decodeFrame(serial, buffer)

      // 零拷贝把 bitmap 传出，所有权一并移交主线程，由主线程负责 close()
      postMessage({ serial, bitmap }, [bitmap])
      bitmap = null
    }
    catch (err) {
      console.error('decode error', err)
      // 传递失败时帧还在 worker 手里，必须自己释放，否则要等 GC 才回收原生内存
      bitmap?.close?.()
    }
  }

  q.running = false
}

// -------------------------
// 3. Base64 → Uint8Array（最快路径）
// -------------------------
function base64ToBuffer(base64) {
  const binary = atob(base64)
  const len = binary.length
  const buf = new Uint8Array(len)
  for (let i = 0; i < len; i++) {
    buf[i] = binary.charCodeAt(i)
  }
  return buf
}
