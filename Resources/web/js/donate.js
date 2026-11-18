// Xiaowei iOS - UI Extensions
(function () {
  if (typeof window === 'undefined' || window.__xwDonateInited) return;
  window.__xwDonateInited = true;

  function initDonate() {
    if (document.getElementById('xw-donate-styles')) return;

    const style = document.createElement('style');
    style.id = 'xw-donate-styles';
    style.textContent = `
      .xw-donate-top-btn {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(249, 115, 22, 0.18));
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.35);
        border-radius: 999px;
        padding: 3px 12px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
        user-select: none;
        margin-right: 12px;
        z-index: 2100;
        -webkit-app-region: no-drag;
      }
      .xw-donate-top-btn:hover {
        background: linear-gradient(135deg, #ef4444, #f97316);
        color: #ffffff;
        border-color: transparent;
        transform: translateY(-1px) scale(1.03);
        box-shadow: 0 4px 14px rgba(239, 68, 68, 0.4);
      }
      .xw-floating-donate {
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 9999;
        display: inline-flex;
        align-items: center;
        gap: 7px;
        background: linear-gradient(135deg, #10b981, #059669);
        color: #ffffff;
        padding: 8px 16px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        box-shadow: 0 6px 22px rgba(16, 185, 129, 0.42);
        transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
        user-select: none;
        -webkit-app-region: no-drag;
      }
      .xw-floating-donate:hover {
        transform: translateY(-2px) scale(1.05);
        box-shadow: 0 8px 28px rgba(16, 185, 129, 0.6);
      }
      .xw-modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: rgba(0, 0, 0, 0.72);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        z-index: 100000;
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.25s ease;
      }
      .xw-modal-overlay.xw-show {
        opacity: 1;
        pointer-events: auto;
      }
      .xw-modal-card {
        width: 92%;
        max-width: 440px;
        max-height: 92vh;
        overflow-y: auto;
        background: #181a20;
        color: #f8fafc;
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 24px;
        padding: 26px 24px 22px 24px;
        box-shadow: 0 28px 70px rgba(0, 0, 0, 0.75);
        position: relative;
        transform: scale(0.92);
        transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        -webkit-app-region: no-drag;
      }
      .xw-modal-overlay.xw-show .xw-modal-card {
        transform: scale(1);
      }
      .xw-modal-close {
        position: absolute;
        top: 14px;
        right: 16px;
        background: rgba(255, 255, 255, 0.08);
        border: none;
        color: #94a3b8;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        font-size: 20px;
        line-height: 1;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
      }
      .xw-modal-close:hover {
        background: rgba(239, 68, 68, 0.25);
        color: #ef4444;
      }
      .xw-modal-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
        border-radius: 999px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 600;
        margin-bottom: 8px;
      }
      .xw-modal-title {
        font-size: 19px;
        font-weight: 700;
        color: #ffffff;
        margin: 0 0 6px 0;
      }
      .xw-modal-sub {
        font-size: 12.5px;
        color: #94a3b8;
        line-height: 1.5;
        margin: 0 0 16px 0;
        padding: 0 6px;
      }
      .xw-qr-wrap {
        background: #ffffff;
        border-radius: 18px;
        padding: 8px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
        margin-bottom: 18px;
        display: inline-block;
      }
      .xw-qr-img {
        display: block;
        width: 240px;
        height: auto;
        border-radius: 12px;
      }
      .xw-info-table {
        width: 100%;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        text-align: left;
        margin-bottom: 18px;
      }
      .xw-info-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 12.5px;
      }
      .xw-info-k {
        color: #94a3b8;
      }
      .xw-info-v {
        font-weight: 600;
        color: #f1f5f9;
      }
      .xw-info-v-hl {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 15px;
        font-weight: 700;
        color: #34d399;
        letter-spacing: 0.5px;
      }
      .xw-copy-btn {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.35);
        border-radius: 8px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.15s;
      }
      .xw-copy-btn:hover {
        background: #10b981;
        color: #ffffff;
      }
      .xw-close-btn {
        width: 100%;
        background: rgba(255, 255, 255, 0.08);
        color: #cbd5e1;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 10px 0;
        font-size: 13.5px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
      }
      .xw-close-btn:hover {
        background: rgba(255, 255, 255, 0.15);
        color: #ffffff;
      }
    `;
    document.head.appendChild(style);

    const overlay = document.createElement('div');
    overlay.id = 'xw-donate-overlay';
    overlay.className = 'xw-modal-overlay';
    overlay.innerHTML = `
      <div class="xw-modal-card" onclick="event.stopPropagation()">
        <button class="xw-modal-close" onclick="window.closeDonateModal()">&times;</button>
        <div class="xw-modal-badge">☕ Ủng hộ tác giả</div>
        <h2 class="xw-modal-title">Ủng Hộ Dự Án Xiaowei iOS 💖</h2>
        <p class="xw-modal-sub">
          Cảm ơn bạn đã tin dùng ứng dụng! Mọi sự đóng góp của bạn đều là nguồn động viên quý giá giúp tác giả tiếp tục cập nhật và hỗ trợ người dùng hoàn toàn miễn phí.
        </p>
        <div class="xw-qr-wrap">
          <img src="/images/donate_qr.jpg" alt="VietQR BIDV VU VAN BIEN" class="xw-qr-img" />
        </div>
        <div class="xw-info-table">
          <div class="xw-info-row">
            <span class="xw-info-k">👤 Chủ tài khoản:</span>
            <span class="xw-info-v">VU VAN BIEN</span>
          </div>
          <div class="xw-info-row">
            <span class="xw-info-k">🏦 Ngân hàng:</span>
            <span class="xw-info-v">BIDV (TMCP Đầu tư & Phát triển Việt Nam)</span>
          </div>
          <div class="xw-info-row">
            <div>
              <div class="xw-info-k">💳 Số tài khoản:</div>
              <div class="xw-info-v-hl">4270572688</div>
            </div>
            <button class="xw-copy-btn" onclick="window.copyDonateText('4270572688', this)">📋 Sao chép</button>
          </div>
          <div class="xw-info-row">
            <div>
              <div class="xw-info-k">💬 Lời nhắn:</div>
              <div class="xw-info-v" style="color: #fbbf24;">Ung ho Xiaowei iOS</div>
            </div>
            <button class="xw-copy-btn" onclick="window.copyDonateText('Ung ho Xiaowei iOS', this)">📋 Sao chép</button>
          </div>
        </div>
        <button class="xw-close-btn" onclick="window.closeDonateModal()">Đóng lại</button>
      </div>
    `;
    overlay.onclick = () => window.closeDonateModal();
    document.body.appendChild(overlay);

    window.openDonateModal = function () {
      const el = document.getElementById('xw-donate-overlay');
      if (el) el.classList.add('xw-show');
    };
    window.closeDonateModal = function () {
      const el = document.getElementById('xw-donate-overlay');
      if (el) el.classList.remove('xw-show');
    };
    window.copyDonateText = function (text, btn) {
      try {
        navigator.clipboard.writeText(text);
      } catch (_) {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      if (btn) {
        const orig = btn.innerText;
        btn.innerText = '✓ Đã chép!';
        btn.style.background = '#10b981';
        btn.style.color = '#fff';
        setTimeout(() => {
          btn.innerText = orig;
          btn.style.background = '';
          btn.style.color = '';
        }, 1800);
      }
    };

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        window.closeDonateModal();
      }
    });

    const floatBtn = document.createElement('div');
    floatBtn.className = 'xw-floating-donate';
    floatBtn.innerHTML = '<span>☕</span><span>Ủng hộ</span>';
    floatBtn.title = 'Ủng hộ tác giả (Donate) - Vũ Văn Biên';
    floatBtn.onclick = () => window.openDonateModal();
    document.body.appendChild(floatBtn);

    function tryInjectTopBtn() {
      const titleBar = document.querySelector('.app-title-bar');
      if (titleBar && !document.getElementById('xw-top-donate-btn')) {
        const topBtn = document.createElement('button');
        topBtn.id = 'xw-top-donate-btn';
        topBtn.className = 'xw-donate-top-btn';
        topBtn.innerHTML = '<span>💖</span><span>Ủng hộ tác giả</span>';
        topBtn.title = 'Ủng hộ dự án Xiaowei iOS (Donate) - Vũ Văn Biên';
        topBtn.onclick = (e) => {
          e.stopPropagation();
          window.openDonateModal();
        };
        const firstControlBtn = titleBar.querySelector('.title-bar-btn');
        if (firstControlBtn) {
          titleBar.insertBefore(topBtn, firstControlBtn);
        } else {
          titleBar.appendChild(topBtn);
        }
      }
    }
    setInterval(tryInjectTopBtn, 1000);
    tryInjectTopBtn();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDonate);
  } else {
    initDonate();
  }
})();
