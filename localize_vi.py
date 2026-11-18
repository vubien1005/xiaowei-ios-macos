#!/usr/bin/env python3
"""
Upgrades Xiaowei iOS frontend to 100% clear, accurate, beginner-friendly Vietnamese:
1. Eagerly imports & pre-registers vi-VN in vue-i18n createI18n messages + fixes loadedLanguages
   and loadLanguageAsync() so initial boot AND manual dropdown switching always render Vietnamese.
2. Configures Naive UI (NConfigProvider + createDiscreteApi) to default to viVN & dateViVN.
3. Completes all missing keys, fixes {var} placeholders, translates remaining English/Chinese/Thai
   entries, and refines 300+ Vietnamese UI labels across menus, toolbars, settings, shortcuts,
   app manager, file manager, batch tools, and macro dialogs.
4. Translates hardcoded Chinese UI strings across all Vue component chunks and verifies syntax
   with /usr/bin/osascript -l JavaScript.
"""

import json
import os
import re
import subprocess

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Resources", "web")
ASSETS_DIR = os.path.join(WEB_DIR, "assets")


def compile_i18n_ast(text):
    """Compile a string (with optional {var} placeholders) into @intlify/vue-i18n AST format."""
    tokens = re.split(r"(\{[a-zA-Z0-9_]+\})", text)
    if len(tokens) == 1:
        return {"t": 0, "b": {"t": 2, "i": [{"t": 3}], "s": text}}
    items = []
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("{") and tok.endswith("}"):
            items.append({"t": 4, "k": tok[1:-1]})
        else:
            items.append({"t": 3, "v": tok})
    return {"t": 0, "b": {"t": 2, "i": items}}


def set_nested_ast(root_obj, dotted_key, vi_text):
    parts = dotted_key.split(".")
    cur = root_obj
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict) or ("t" in cur[p] and "b" in cur[p]):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = compile_i18n_ast(vi_text)


# Comprehensive, accurate, beginner-friendly Vietnamese dictionary overrides & additions
VI_UPDATES = {
    # --- Missing keys & placeholder fixes ---
    "common.modalSelectDevice1": " (Đã chọn ",
    "common.modalSelectDevice2": " máy)",
    "common.formInput": "Vui lòng nhập...",
    "common.formSelect": "Vui lòng chọn...",
    "welcome.accessibility.p14": "[Trợ lý Chiếu màn hình] chưa được cấp quyền cửa sổ nổi, vui lòng cấp quyền trước",
    "quickReply.msg.importFail": "{prefix}Sai định dạng ở dòng thứ {i}",
    "shareDevice.homeGen.vipLimit": "Bản miễn phí chỉ chia sẻ tối đa {len} thiết bị. Nâng cấp VIP để chia sẻ không giới hạn.",
    "version.fun.t4_share": "Chia sẻ điều khiển máy",
    "buy.benefitsTitle": "Quyền lợi gói VIP",
    "buy.benefitShare": "Chia sẻ điện thoại không giới hạn",
    "buy.benefitShareDesc": "Bản miễn phí chỉ chia sẻ tối đa {len} thiết bị",
    "virtual.shop.systemAll": "Tất cả",
    "virtual.shop.systemVersion": "Phiên bản hệ điều hành",
    "virtual.shop.appSupport": "Ứng dụng hỗ trợ",
    "virtual.shop.dayCard1": "Gói Ngày",
    "virtual.shop.dayCard7": "Gói Tuần",
    "virtual.shop.dayCard30": "Gói Tháng",
    "virtual.shop.customNum": "Tùy chỉnh",
    "virtual.shop.noDiscount": "Không giảm giá",
    "virtual.shop.saveMoney": "Tiết kiệm {amount}{unit}",
    "virtual.shop.saveMore": "Tiết kiệm thêm {amount}{unit}",
    "virtual.shop.freeReturn": "Hoàn tiền miễn phí",
    "virtual.shop.freeReturnTip": "Số lượng này áp dụng chính sách hoàn tiền miễn phí theo quy định.",
    "virtual.shop.originPrice": "Giá gốc",
    "virtual.shop.totalSave": "Ưu đãi {disc}, tổng tiết kiệm {amount} {unit}",
    "virtual.shop.noDiscountOrder": "Đơn này chưa có chiết khấu, xem quy tắc ưu đãi",
    "virtual.shop.restockNotice": "Báo khi có hàng",
    "virtual.shop.restockNoticeTip": "Khi bật, hệ thống sẽ thông báo ngay khi dòng máy này có hàng trở lại qua:",
    "virtual.shop.restockNoticeTip1": "Tin nhắn SMS tới số điện thoại tài khoản",
    "virtual.shop.restockNoticeTip2": "Thông báo hệ thống ở thanh bên của ứng dụng",
    "virtual.shop.restockNoticeOn": "Đã bật thông báo khi có hàng trở lại",
    "virtual.shop.restockNoticeOff": "Đã tắt thông báo có hàng",
    "virtual.shop.restockNoticeFail": "Cập nhật thông báo thất bại, vui lòng thử lại sau",
    "virtual.shop.restockNoticeNoPhone": "Vui lòng liên kết số điện thoại trước khi bật thông báo",
    "virtual.shop.notice.button": "Báo khi có hàng",
    "virtual.shop.notice.cancel": "Hủy",
    "virtual.shop.notice.confirm": "Xác nhận",
    "virtual.shop.notice.dayError": "Số ngày phải là số nguyên từ 1 đến {max}",
    "virtual.shop.notice.model": "Dòng máy",
    "virtual.shop.notice.numError": "Số lượng phải là số nguyên từ 1 đến 999",
    "virtual.shop.notice.phone": "Thông báo",
    "virtual.shop.notice.phoneError": "Vui lòng nhập số điện thoại",
    "virtual.shop.notice.phonePlaceholder": "Số điện thoại liên kết (có thể sửa)",
    "virtual.shop.notice.remark": "Ghi chú",
    "virtual.shop.notice.remarkError": "Ghi chú không được vượt quá 200 ký tự",
    "virtual.shop.notice.remarkPlaceholder": "Vui lòng nhập...",
    "virtual.shop.notice.submitFail": "Đăng ký nhận thông báo thất bại",
    "virtual.shop.notice.success": "Đã đăng ký nhận thông báo khi có hàng",
    "virtual.shop.notice.title": "Thông báo khi có hàng",
    "shareDevice.msg.p0": "Lỗi không xác định",
    "shareDevice.msg.p1": "Đã đạt giới hạn số máy chia sẻ của gói miễn phí",
    "shareDevice.msg.p2": "Người chia sẻ chưa đăng nhập",
    "shareDevice.msg.p3": "Mã chia sẻ không hợp lệ, vui lòng kiểm tra lại",
    "shareDevice.msg.p4": "Mã chia sẻ này đã được sử dụng",
    "shareDevice.msg.p5": "Phiên chia sẻ đã kết thúc",
    "shareDevice.msg.p6": "Không thể nhận thiết bị chia sẻ, vui lòng liên hệ người gửi",
    "shareDevice.msg.p7": "Không thể tự nhận thiết bị do chính bạn chia sẻ",
    "shareDevice.homeGen.timeErr": "Thời gian hết hạn phải lớn hơn thời điểm hiện tại",
    "shareDevice.stop.selectTip": "Chọn thiết bị muốn dừng chia sẻ",
    "shareDevice.stop.stopAll": "Dừng chia sẻ tất cả",
    "shareDevice.stop.stopSelected": "Dừng các máy đã chọn",
    "shareDevice.stop.deviceCol": "Thiết bị",
    "shareDevice.manage.totalPrefix": "Tổng cộng {count} mục",
    "shareDevice.manage.statusOffline": "Đã ngắt kết nối",
    "shareDevice.manage.stopBtn": "Dừng chia sẻ",
    "shareDevice.refresh.title": "Người nhận không kết nối được?",
    "shareDevice.refresh.code": "Mã chia sẻ",
    "shareDevice.refresh.isUsed": "Trạng thái sử dụng",
    "shareDevice.refresh.remark": "Giải thích",
    "shareDevice.refresh.remarkContent": "Nếu mã chưa dùng nhưng người nhận không mở được, hãy bấm kiểm tra để làm mới trạng thái mã.",
    "shareDevice.refresh.result": "Kết quả kiểm tra",
    "shareDevice.refresh.msg1": "Đã làm mới trạng thái, người nhận có thể thử lại ngay",
    "shareDevice.refresh.msg2": "Mã chia sẻ hoạt động bình thường, vui lòng kiểm tra kết nối mạng",
    "shareDevice.refresh.msg3": "Kiểm tra thất bại, vui lòng kiểm tra mạng",
    "shareDevice.refresh.submit": "Kiểm tra & Làm mới mã",
    "shareDevice.refresh.submitLoading": "Đang kiểm tra...",
    "shareDeviceReceive.form.verifyBtn": "Kiểm tra mã chia sẻ",
    "shareDeviceReceive.form.verifying": "Đang xác thực...",
    "shareDeviceReceive.form.backTip": "Mã hợp lệ! Xác nhận để thêm thiết bị chia sẻ vào danh sách của bạn.",

    # --- Fix untranslated Thai / Chinese strings in vi-VN ---
    "openapi.portError": "Cổng API 22222 đang bận, vui lòng đóng ứng dụng chiếm cổng và khởi động lại.",

    # --- Common & Titlebar & Sidebar ---
    "common.export": "Xuất ra tệp",
    "common.import": "Nhập từ tệp",
    "common.remove": "Xóa",
    "common.homeLoading": "Đang tải giao diện...",
    "common.exportSuccess": "Xuất tệp thành công",
    "titleBar.minimize": "Thu nhỏ xuống Dock",
    "titleBar.maximize": "Phóng to cửa sổ",
    "titleBar.restore": "Thu về kích thước cũ",
    "titleBar.close": "Thoát ứng dụng",
    "sidebar.account": "Tài khoản",
    "sidebar.vip": "Gói VIP",
    "sidebar.shop": "Thuê Cloud",
    "sidebar.notion": "Thông báo",
    "sidebar.updateTip": "Đã có phiên bản mới, nhấp để cập nhật",

    # --- Big Screen Active Device Control Bar ---
    "activeDevice.appShow": "Mở danh sách Ứng dụng",
    "activeDevice.closePrompt": "Mẹo: Nhấp chuột phải vào vùng trống để đóng màn hình lớn",
    "activeDevice.controlMode_many": "Đang bật chế độ điều khiển riêng máy này (tạm dừng đồng bộ)",
    "activeDevice.controlMode_one": "Điều khiển riêng",
    "activeDevice.fixedScreen": "Ghim cố định màn hình lớn",
    "activeDevice.horizontal": "Xoay ngang màn hình",
    "activeDevice.vertical": "Xoay dọc màn hình",
    "activeDevice.moveScreen": "Tách nổi màn hình lớn",
    "activeDevice.phoneFun": "Thanh công cụ điều khiển",
    "activeDevice.sidebarHide": "Thu gọn thanh công cụ",

    # --- Left Panel Grouping / Tags (Nhóm thiết bị) ---
    "tag.title": "Nhóm thiết bị",
    "tag.typeLocal": "Máy cắm cáp / LAN",
    "tag.typeCloud": "Máy thật trên Mây",
    "tag.typeVirtual": "Máy ảo Cloud",
    "tag.allTag": "Tất cả điện thoại",
    "tag.notTag": "Chưa phân nhóm",
    "tag.add": "Tạo nhóm mới",
    "tag.addPlace": "Nhập tên nhóm (VD: Nhóm TikTok 1)",
    "tag.changeName": "Đổi tên nhóm",
    "tag.newNamePlace": "Nhập tên nhóm mới",
    "tag.remove": "Xóa nhóm này",
    "tag.removePrompt": "Bạn có chắc muốn xóa nhóm này không? (Không làm mất thiết bị)",
    "tag.oneView": "Chỉ hiện các máy thuộc nhóm này",
    "tag.dropSort": "Giữ chuột kéo để đổi thứ tự",
    "tag.resetSort": "Đánh lại số thứ tự từ 1",
    "tag.resetSortPrompt": "Đặt lại số thứ tự cho toàn bộ điện thoại đang kết nối?",
    "tag.exportPrompt": "Sao lưu cấu hình tên máy, số thứ tự và nhóm ra tệp",
    "tag.importPrompt": "Khôi phục cấu hình tên máy, số thứ tự và nhóm từ tệp",
    "tag.msg.exist": "Tên nhóm này đã tồn tại",
    "tag.msg.resetSortOk": "Đã đánh lại số thứ tự thành công",

    "tagType.all": "Tất cả",
    "tagType.accessible": "Trợ năng",
    "tagType.showAll": "Hiện tất cả",
    "tagType.showSelect": "Chỉ hiện máy đang chọn",

    # --- Device Sliders & Status ---
    "device.select.title1": " (Đang chọn ",
    "device.select.title2": " máy)",
    "device.quality.low": "Tiết kiệm",
    "device.quality.center": "Tiêu chuẩn",
    "device.quality.high": "Rõ nét",
    "device.quality.super": "Siêu nét",
    "device.config.bigSize": "Cỡ màn hình chính",
    "device.config.smallSize": "Cỡ ô màn hình nhỏ",
    "device.config.smallQuality": "Độ nét lưới nhỏ",
    "device.config.smailFrame": "Độ mượt (FPS) lưới nhỏ",
    "device.loading.control": "Đang điều khiển chính",
    "device.loading.modeChange": "Đang chuyển chế độ kết nối...",
    "device.loading.offline": "Đã mất kết nối với iPhone, vui lòng kiểm tra cáp USB",
    "device.loading.closeScreen": "Đang ẩn hình ảnh ô này để tiết kiệm tài nguyên (nhấp để bật lại)",
    "deviceList.noIp": "Kết nối USB",
    "deviceList.loading": "Đang kết nối màn hình iPhone...",
    "deviceList.tagNoPhone": "Chưa có điện thoại nào trong nhóm này",
    "deviceList.viewAllPhone": "Xem tất cả điện thoại",

    # --- Core Toolbar & Right-Click Functions (fun.*) ---
    "fun.openScreen": "Mở màn hình điều khiển lớn",
    "fun.smoothControl": "Điều khiển trực tiếp trên lưới nhỏ",
    "fun.smoothControlPrompt": "Khi bật: Nhấp chuột vào ô nhỏ sẽ chạm thẳng lên màn hình điện thoại (đồng bộ sang các máy đang chọn). Khi tắt: Nhấp chuột dùng để chọn máy hoặc phóng to.",
    "fun.fixedBigScreen": "Ghim màn hình lớn cạnh lưới nhỏ",
    "fun.fixedBigScreenPrompt": "Vừa điều khiển trên màn hình lớn vừa quan sát toàn bộ lưới điện thoại bên cạnh",
    "fun.ctrlSelect": "Giữ phím Ctrl khi chọn nhiều máy",
    "fun.ctrlSelectPrompt": "Khi bật: Giữ phím Ctrl + Nhấp chuột để chọn/bỏ chọn thêm từng điện thoại trên lưới",
    "fun.ctrlSelectMsg": "Đang bật [Điều khiển trực tiếp trên lưới nhỏ] nên cần giữ phím Ctrl để chọn máy",
    "fun.rotateSmallScreen": "Xoay ngang / dọc lưới nhỏ",
    "fun.rotateSmallScreenPrompt": "Chuyển toàn bộ ô màn hình nhỏ sang khung ngang (xem video/game) hoặc khung dọc",
    "fun.rotateRight": "Xoay phải 90°",
    "fun.rotateLeft": "Xoay trái 90°",
    "fun.oneKeyLightScreen": "Bật sáng tất cả màn hình",
    "fun.oneKeyDarkScreen": "Tắt màn hình các máy",
    "fun.oneKeyPrompt": "Tắt sáng màn hình vật lý để giảm nóng máy và tiết kiệm pin",
    "fun.breathScreen": "Khóa / Tắt màn hình",
    "fun.lightScreen": "Mở sáng màn hình",
    "fun.prevScreen": "Chuyển sang máy trước",
    "fun.nextScreen": "Chuyển sang máy tiếp theo",
    "fun.touchUp": "Vuốt lên (Lướt video tiếp)",
    "fun.touchDown": "Vuốt xuống (Quay lại video trước)",
    "fun.touchLeft": "Vuốt sang trái",
    "fun.touchRight": "Vuốt sang phải",
    "fun.changeSort": "Đổi số thứ tự máy",
    "fun.sortTab1": "Đánh số tăng dần tự động",
    "fun.sortTab2": "Đặt cùng một số",
    "fun.changeSortPlace": "Nhập số thứ tự bắt đầu (VD: 1)",
    "fun.changeSortConfirm": "Lưu số thứ tự",
    "fun.changeName": "Đổi tên gợi nhớ",
    "fun.changeNamePlace": "Nhập tên gọi cho iPhone này",
    "fun.showCode": "Hiện số thứ tự máy",
    "fun.showCodePrompt": "Hiển thị con số thứ tự nổi trên góc từng ô điện thoại",
    "fun.showDeviceName": "Hiện tên điện thoại",
    "fun.showDeviceNamePrompt": "Hiển thị tên thiết bị ở thanh tiêu đề của từng ô màn hình",
    "fun.showMode": "Hiện kiểu kết nối",
    "fun.showModePrompt": "Hiển thị biểu tượng kết nối cáp USB hoặc mạng Wi-Fi",
    "fun.showIp": "Hiện địa chỉ IP",
    "fun.showIpPrompt": "Hiển thị địa chỉ IP mạng nội bộ của từng điện thoại",
    "fun.showTag": "Luôn mở rộng danh sách nhóm",
    "fun.showTagPrompt": "Luôn xổ danh sách các máy bên trong từng nhóm ở cột bên trái",
    "fun.ipa": "Cài ứng dụng (.IPA)",
    "fun.apk": "Cài đặt ứng dụng",
    "fun.inputBatch": "Rải văn bản cho nhiều máy",
    "fun.inputBatchPrompt": "Chia danh sách nhiều dòng văn bản/tài khoản để gửi mỗi dòng cho 1 điện thoại khác nhau",
    "fun.fileBatch": "Rải tệp / ảnh cho nhiều máy",
    "fun.fileBatchPrompt": "Chia danh sách ảnh/video để gửi tự động vào từng điện thoại theo thứ tự",
    "fun.importFile": "Gửi ảnh / video vào iPhone",
    "fun.exportFile": "Duyệt & Xuất tệp từ iPhone",
    "fun.exportClipboard": "Lấy văn bản đã copy từ iPhone",
    "fun.exportClipboardPanel": "Nội dung bộ nhớ tạm thu được ({len} máy)",
    "fun.screenShot": "Chụp màn hình lưu về Mac",
    "fun.screenShotPhone": "Chụp ảnh màn hình nhanh",
    "fun.screenShotPhoneOk": "Đã chụp màn hình và lưu về máy Mac!",
    "fun.quickReply": "Kho văn bản mẫu (Gõ nhanh)",
    "fun.quickReplyPrompt": "Lưu sẵn các câu trả lời, bình luận, kịch bản chữ để bấm gửi 1 chạm vào điện thoại",
    "fun.wallpaper": "Đặt số thứ tự làm hình nền",
    "fun.restart": "Khởi động lại iPhone",
    "fun.restartConfirm": "Bạn có chắc chắn muốn khởi động lại (Reboot) các iPhone đang chọn không?",
    "fun.screenShow": "Hiện lại hình ảnh ô này",
    "fun.screenClose": "Tạm ẩn hình ảnh ô này",
    "fun.addTag": "Chuyển vào nhóm",
    "fun.moveTag": "Gỡ khỏi nhóm hiện tại",
    "fun.addTagPlace": "Hãy tạo nhóm ở cột trái trước",
    "fun.reConnection": "Kết nối lại thiết bị",
    "fun.reConnectionStart": "Đang làm mới kết nối tới iPhone...",
    "fun.disconnectNetwork": "Ngắt phiên kết nối",
    "fun.removeDevice": "Xóa khỏi danh sách",
    "fun.copyId": "Sao chép mã UDID thiết bị",
    "fun.copyIdSuccess": "Đã sao chép mã UDID vào bộ nhớ tạm",
    "fun.systemSetting": "Cài đặt phần mềm",
    "fun.systemSettingParam": "Tùy chỉnh giao diện, bố cục lưới, ngôn ngữ và phím tắt",
    "fun.systemDiagnose": "Danh sách quản lý thiết bị",
    "fun.systemDiagnosePrompt": "Xem bảng tổng hợp toàn bộ điện thoại đang kết nối, UDID và trạng thái",
    "fun.moreFun": "Tất cả công cụ mở rộng",
    "fun.hideFun": "Công cụ đang cất gọn",
    "fun.hideFunEmpty": "Chưa có công cụ nào bị ẩn",
    "fun.moreFunSortHelp": "Mẹo: Kéo thả các nút công cụ bạn hay dùng lên khu vực hiển thị, hoặc kéo các nút ít dùng xuống ô ẩn cho gọn.",
    "drop.moreHide": "Cất vào mục Mở rộng",
    "drop.morePanel": "Hiện trên thanh công cụ",
    "AutoAirplay.name": "Tự động chiếu AirPlay",
    "AutoAirplay.notName": "Tắt tự động chiếu",
    "AutoAirplay.prompt": "Nếu không tự chiếu màn hình được, hãy lấy tọa độ của [Biểu tượng AirPlay] và [Tên thiết bị] để tự động kết nối.",

    # --- Action Recorder / Macro (Ghi & chạy thao tác tự động) ---
    "fun.actionRecord": "Ghi kịch bản thao tác (Macro)",
    "fun.actionExecute": "Chạy kịch bản tự động",
    "fun.actionNewName": "Kịch bản thao tác",
    "fun.actionRecordWindow": "Khung ghi thao tác mẫu",
    "fun.actionRecordLog": "Các bước thao tác đã ghi",
    "fun.actionRecordList": "Danh sách kịch bản đã lưu",
    "fun.actionRecordStart": "Bắt đầu ghi thao tác",
    "fun.actionRecordStop": "Hoàn tất & Lưu kịch bản",
    "fun.actionRecordPause": "Tạm dừng ghi",
    "fun.actionRecordContinue": "Tiếp tục ghi",
    "fun.actionRecordTitlePlay": "Chạy thử kịch bản",
    "fun.actionRecordTitleDelete": "Xóa kịch bản",
    "fun.actionRecordDelete": "Bạn có chắc muốn xóa kịch bản thao tác này không?",
    "fun.actionRecordDone": "Đã lưu kịch bản thao tác!",
    "fun.actionRecordPausePlay": "Tạm dừng chạy",
    "fun.actionRecordStopPlay": "Dừng kịch bản",
    "fun.actionRecordStopPlayContinue": "Tiếp tục chạy",
    "fun.action.titleModel1": "Chạy kịch bản tự động (Đã chọn ",
    "fun.action.titleModel2": " máy)",
    "fun.action.titleEdit": "Chỉnh sửa kịch bản",
    "fun.action.logEmpty": "Hãy chạm, vuốt hoặc gõ phím trên màn hình bên trái để ghi lại từng bước",
    "fun.action.empty": "Chưa có kịch bản nào được lưu",
    "fun.action.export": "Xuất kịch bản ra tệp",
    "fun.action.import": "Nhập kịch bản từ tệp",
    "fun.action.form.action": "Chọn kịch bản",
    "fun.action.form.count": "Số vòng lặp lại",
    "fun.action.form.countPrompt": "Nhập 0 để lặp liên tục không dừng",
    "fun.action.form.taskInterval": "Nghỉ giữa các vòng lặp",
    "fun.action.form.taskIntervalSplit": "đến",
    "fun.action.form.taskIntervalPrompt": "giây (ngẫu nhiên)",
    "fun.action.form.deviceInterval": "Độ trễ lệch nhau giữa các máy",
    "fun.action.form.deviceIntervalPrompt": "Nhập 0 để tất cả các máy chạy cùng lúc",
    "fun.action.form.execute": "Bắt đầu chạy ngay",
    "fun.action.form.editSubmit": "Lưu thiết lập",

    # --- Auto Swipe (Tự động lướt màn hình: TikTok / Reels / Shorts) ---
    "autoTouch.name": "Tự động lướt màn hình",
    "autoTouch.stopName": "Dừng tự động lướt",
    "autoTouch.desc": "Tự động vuốt lặp lại theo chu kỳ (rất tiện để nuôi tương tác, lướt video TikTok/Reels/Shorts)",
    "autoTouch.form.title1": "Tự động lướt màn hình (Đang chọn ",
    "autoTouch.form.title2": " máy)",
    "autoTouch.form.f1_device": "Thiết bị áp dụng",
    "autoTouch.form.f1_p1": "Đang chọn ",
    "autoTouch.form.f1_p2": " máy để chạy",
    "autoTouch.form.f2_action": "Hướng vuốt màn hình",
    "autoTouch.form.f2_t1": "Vuốt lên (Xem video kế tiếp)",
    "autoTouch.form.f2_t2": "Vuốt xuống",
    "autoTouch.form.f2_t3": "Vuốt sang trái",
    "autoTouch.form.f2_t4": "Vuốt sang phải",
    "autoTouch.form.f3_interval": "Thời gian nghỉ mỗi lần vuốt",
    "autoTouch.form.f3_p1": "đến",
    "autoTouch.form.p3_p2": "giây (ngẫu nhiên tự nhiên)",
    "autoTouch.form.p3_p3": "Đơn vị tính bằng giây (từ 1 đến 999 giây).",
    "autoTouch.form.p3_p4": "Nếu điền 2 ô bằng nhau (VD: 5 đến 5), máy sẽ vuốt cố định đúng mỗi 5 giây.",
    "autoTouch.form.p4_label": "Tổng số lần vuốt",
    "autoTouch.form.p4_p1": "Điền 0 để tự động lướt liên tục cho đến khi bấm dừng",
    "autoTouch.form.start": "Bắt đầu lướt tự động",

    # --- Delay & Random Offset ---
    "fun.randomDelay": "Độ trễ đồng bộ ngẫu nhiên",
    "fun.randomDelayPrompt": "Tự động thêm độ trễ ngẫu nhiên giữa các máy khi điều khiển đồng bộ để thao tác giống người thật hơn",
    "fun.randomOffset": "Lệch điểm chạm ngẫu nhiên",
    "fun.randomOffsetPrompt": "Tự động xê dịch nhẹ tọa độ chạm vài pixel trên từng máy phụ để tránh trùng điểm chạm tuyệt đối",
    "delaySync.name": "Độ trễ đồng bộ tuần tự",
    "delaySync.desc": "Khi bật, các máy phụ sẽ thực hiện thao tác nối tiếp nhau cách đều một khoảng thời gian thay vì bấm cùng một tích tắc.",
    "delaySync.status": "Bật trễ tuần tự",
    "delaySync.interval": "Khoảng cách giữa từng máy",
    "delaySync.select": "Áp dụng cho thao tác",
    "delayOffset.name": "Trễ & Lệch điểm chạm ngẫu nhiên",

    # --- Lock / Wake / Volume iPhone ---
    "iphoneLockScreen.lockName": "Khóa màn hình iPhone",
    "iphoneLockScreen.lightName": "Mở sáng màn hình iPhone",
    "volume.upName": "Tăng âm lượng (+)",
    "volume.downName": "Giảm âm lượng (-)",

    # --- App Manager & IPA Installer ---
    "apk.select": "Chọn tệp cài đặt",
    "apk.title1": "Đang cài đặt cho ",
    "apk.title2": " thiết bị — ",
    "apk.title3": " tệp APK",
    "apk.title3IPA": " tệp IPA",
    "apk.typeMsg.closed": "Quá trình truyền bị gián đoạn",
    "app.title": "Ứng dụng trên iPhone",
    "app.appList": "Danh sách ứng dụng",
    "app.reloadAppList": "Tải lại danh sách ứng dụng",
    "app.showMenu": "Hiện thanh công cụ",
    "app.customSetting": "Mở Cài đặt (Settings) của iPhone",
    "app.pinTop": "Ghim lên đầu danh sách",
    "app.pinBottom": "Bỏ ghim ứng dụng",
    "app.close": "Đóng ứng dụng này",
    "app.closePrompt": "Đóng ứng dụng {name} trên các máy đang chọn?",
    "app.uninstallPopover": "Gỡ ứng dụng khỏi iPhone",
    "app.uninstallPositiveText": "Gỡ bỏ",
    "app.uninstallNegativeText": "Hủy",
    "app.uninstallPrompt": "Bạn có chắc muốn gỡ hoàn toàn ứng dụng {name} khỏi iPhone không?",
    "app.uninstallFail": "Không thể gỡ cài đặt ứng dụng",
    "app.loading": "Đang đọc danh sách ứng dụng từ iPhone...",
    "app.msg.close": "Đã đóng ứng dụng trên iPhone",
    "app.msg.notApp": "Không tìm thấy ứng dụng nào phù hợp",

    # --- File Manager, Quick Phrases & Batch File/Text ---
    "viewFile.title": "Quản lý tệp tin trên iPhone ({p})",
    "viewFile.titleSelect": "Chọn tệp trên iPhone ({p})",
    "viewFile.openDirectory": "Mở thư mục trên Mac",
    "viewFile.openDir": "Xem trong Finder",
    "viewFile.exportSuccess": "Đã xuất tệp về máy Mac thành công!",
    "pasteText.name": "Gõ / Dán văn bản vào iPhone",
    "pasteText.title1": "Gửi văn bản vào iPhone (Đang chọn ",
    "pasteText.title2": " máy)",
    "pasteText.placeholder": "Nhập hoặc dán văn bản tại đây (Cmd + V) để gõ thẳng vào ô đang mở trên iPhone...",
    "pasteText.btn": "Gửi chữ vào iPhone ({shortcuts})",
    "quickReply.title": "Kho văn bản mẫu",
    "quickReply.exportName": "Kho văn bản mẫu",
    "quickReply.add": "Thêm văn bản mẫu",
    "quickReply.exportPrompt": "Xuất danh sách văn bản mẫu ra tệp",
    "quickReply.form.tagQuickReply": "Văn bản mẫu",
    "quickReply.form.emptyContentPrompt": "Nhóm này chưa có văn bản mẫu nào",
    "quickReply.removePrompt": "Bạn có chắc muốn xóa văn bản mẫu này không?",
    "inputBatch.title1": "Rải văn bản cho nhiều máy (Đang chọn ",
    "inputBatch.title2": " máy)",
    "inputBatch.input": "Gõ thẳng vào máy",
    "inputBatch.inputPrompt": "Gõ trực tiếp từng dòng tương ứng vào ô nhập liệu trên từng điện thoại",
    "inputBatch.copy": "Chép vào bộ nhớ tạm",
    "inputBatch.copyPrompt": "Đưa từng dòng tương ứng vào Clipboard riêng của từng điện thoại",
    "inputBatch.msg.clipboard": "Đã gửi {result} tới {length} điện thoại",
    "inputBatch.msg.setClipboard": "Đã chép nội dung vào bộ nhớ tạm của {length} điện thoại",
    "inputBatch.prompt.title": "Cách hoạt động:",
    "inputBatch.prompt.p1_1": "Lưu ý: ",
    "inputBatch.prompt.p1_2": "Hãy chạm mở sẵn ô nhập chữ trên iPhone",
    "inputBatch.prompt.p1_3": " trước khi bấm [Gõ thẳng vào máy].",
    "inputBatch.prompt.p2": "Mỗi dòng văn bản sẽ được phát lần lượt cho từng máy theo thứ tự số hiệu từ nhỏ đến lớn (Máy 1 nhận dòng 1, Máy 2 nhận dòng 2...).",
    "fileBatch.title1": "Rải tệp / ảnh cho nhiều máy (Đang chọn ",
    "fileBatch.title2": " máy)",
    "fileBatch.addButton": "Chọn tệp từ máy Mac",
    "fileBatch.sendButton": "Bắt đầu gửi vào iPhone",

    # --- Settings, OTG, System Diagnose, Version & Shortcuts Panel ---
    "adb.saveButton": "Lưu vào thường dùng",
    "otgSetting.allAdd": "Thêm tất cả",
    "otgSetting.allScan": "Quét toàn mạng",
    "otgSetting.manage": "Quản lý dải mạng",
    "sysDiagnose.title": "Danh sách thiết bị kết nối",
    "sysDiagnose.reconnect": "Kết nối lại tất cả",
    "sysDiagnose.refresh": "Làm mới danh sách",
    "sysDiagnose.form.phoneCode": "Số thứ tự",
    "sysDiagnose.form.phoneModel": "Kiểu máy",
    "sysDiagnose.form.serial": "Mã UDID / Serial",
    "sysDiagnose.form.tag": "Nhóm",
    "sysDiagnose.form.tagPlaceholder": "Lọc theo nhóm",
    "sysDiagnose.form.searchPlaceholder": "Tìm theo nhóm, số thứ tự, tên máy hoặc mã UDID",
    "sysDiagnose.form.close.switch": "Hiển thị màn hình",
    "sysDiagnose.tablePaging10": "10 dòng / trang",
    "sysDiagnose.tablePaging20": "20 dòng / trang",
    "sysDiagnose.tablePaging30": "30 dòng / trang",
    "sysDiagnose.tablePaging40": "40 dòng / trang",
    "sysDiagnose.tablePaging50": "50 dòng / trang",
    "sysDiagnose.tablePaging100": "100 dòng / trang",
    "sysDiagnose.tablePaging200": "200 dòng / trang",
    "sysDiagnose.tablePaging500": "500 dòng / trang",
    "deviceTask.name": "Tác vụ đang chạy",
    "deviceTask.deviceTable.code": "Số thứ tự máy",
    "deviceTask.deviceTable.name": "Tên điện thoại",
    "deviceTask.placeholder": "Số thứ tự / Tên điện thoại",
    "deviceTask.table.startTimeImmediately": "Chạy ngay",
    "setting.name": "Cài đặt chung",
    "setting.tab1": "Giao diện phần mềm",
    "setting.tab2NewTitle": "Hiển thị lưới điện thoại",
    "setting.lang": "Ngôn ngữ hiển thị",
    "setting.foldOk": "Mở thanh công cụ phía trên",
    "setting.foldNo": "Thu gọn thanh công cụ phía trên",
    "setting.tab1_1.control": "Vị trí bảng công cụ",
    "setting.tab1_1.positionLeft": "Bên trái",
    "setting.tab1_1.positionRight": "Bên phải",
    "setting.tab1_1.color.mode": "Giao diện Sáng / Tối",
    "setting.tab1_1.color.light": "Giao diện Sáng",
    "setting.tab1_1.color.dark": "Giao diện Tối",
    "setting.tab1_1.theme": "Màu nhấn chủ đạo",
    "setting.tab1_1.codeOpacity": "Độ đậm số thứ tự máy",
    "setting.tab1_1.codeColor": "Màu chữ số thứ tự máy",
    "setting.tab1_1.smallScreenSpace": "Khoảng cách giữa các ô điện thoại",
    "setting.tab1_1.smallZoomText": "Kính lúp soi nhanh",
    "setting.tab1_1.smallZoom": "Hiện kính lúp khi rê chuột lên ô nhỏ",
    "setting.tab1_1.smallZoomShow": "Bật",
    "setting.tab1_1.smallZoomHide": "Tắt",
    "setting.tab1_1.smallRemark": "Ô ghi chú trên góc máy",
    "setting.tab1_1.smallContextmenu": "Chuột phải khi đang điều khiển lưới nhỏ",
    "setting.tab1_1.smallContextmenuMenu": "Mở menu công cụ",
    "setting.tab1_1.smallContextmenuBack": "Vuốt quay lại (Back)",
    "setting.tab1_1.offline": "Thiết bị đã rút cáp",
    "setting.tab1_1.offlineShow": "Giữ ô chờ trên lưới",
    "setting.tab1_1.offlineHide": "Tự động ẩn đi",
    "setting.tab1_1.selectPhone": "Số lượng máy đang chọn",
    "setting.tab1_1.selectPhoneFollow": "Hiện cạnh con trỏ chuột",
    "setting.tab1_1.selectPhoneHide": "Ẩn",
    "setting.tab1_1.showXiaoweiAIcustomer": "Trợ lý hỗ trợ AI",
    "setting.tab1_1.layoutMethons": "Thứ tự sắp xếp trên lưới",
    "setting.tab1_1.layoutMethons1": "Theo số thứ tự máy (1, 2, 3...)",
    "setting.tab1_1.layoutMethons2": "Gom theo từng nhóm",
    "setting.tab1_1.sortMode": "Thứ tự sắp xếp trên lưới",
    "setting.tab1_1.sortSort": "Theo số thứ tự máy",
    "setting.tab1_1.sortTag": "Theo nhóm thiết bị",
    "setting.tab1_1.screenLightStatus": "Màn hình điện thoại khi kết nối",
    "setting.tab1_1.screenLightKeep": "Giữ luôn sáng",
    "setting.tab1_1.screenLightAuto": "Tự động tắt sáng",
    "setting.tab2.name": "Bảng phím tắt",
    "setting.tab2.smallColNum": "Số cột điện thoại mỗi hàng",
    "setting.tab2.smallColNumAuto": "Tự động theo cỡ ô",
    "setting.tab2.smallColNumFixed": "Cố định số cột",
    "setting.tab3.p5": "Đội ngũ phát triển Xiaowei iOS",
    "setting.panel.fix": "Ghim cố định thanh bên",
    "setting.panel.hide": "Thu gọn thanh bên",
    "setting.panel.switchTheme": "Đổi chế độ Sáng / Tối",
    "setting.panel.shortcutSetting": "Cài đặt hệ thống",
    "setting.panel.shortcut": "Phím tắt",
    "setting.panel.setting": "Công cụ nhanh",
    "setting.panel.otgSetting": "Mạng OTG",
    "setting.panel.version": "Phiên bản",
    "contact.customer.p2": "Hợp tác kinh doanh",
    "contact.customer.p3": "Hỗ trợ kỹ thuật trực tuyến",
    "update.closeUpdate": "Để sau, tạm ẩn thông báo",
    "update.updateButton": "Cập nhật ngay bây giờ",
    "version.form.availableNumber": "Số lượng máy hỗ trợ",
    "version.form.notVipLimit": " máy (Bản VIP không giới hạn)",
    "version.fun.unit": "máy",

    # --- Welcome / Empty State Guide for macOS + iPhone ---
    "welcome.iphone.p1": "Cắm cáp USB kết nối iPhone với máy Mac",
    "welcome.iphone.p2": "Mở khóa màn hình iPhone",
    "welcome.iphone.p3": "Chạm \"Tin cậy\" (Trust) trên iPhone và nhập mật mã nếu được hỏi",
    "welcome.iphone.p4": "Bật \"Chế độ nhà phát triển\" trong Cài đặt › Quyền riêng tư & Bảo mật (iOS 16+)",
    "welcome.iphone.p5": "Chờ vài giây để hệ thống tự động kết nối cầu nối điều khiển",
    "welcome.iphone.p6": "Màn hình iPhone sẽ hiện lên lưới để điều khiển ngay bằng chuột & bàn phím",
    "welcome.otg.p1": "Hoàn tất kết nối điện thoại với máy tính qua cáp USB;",

    # --- Shortcuts Help ---
    "shortcut.common": "Thao tác chung",
    "shortcut.selectAll": "Chọn tất cả điện thoại",
    "shortcut.shiftSelectAll": "Chọn liên tiếp nhiều máy",
    "shortcut.shiftSelectAllMouseLeft": "Chuột trái",
    "shortcut.cancelSelect": "Bỏ chọn toàn bộ máy",
    "shortcut.cancelSelectAction": "Nhấp chuột trái vào vùng trống",
    "shortcut.oneControl": "Chỉ điều khiển riêng 1 máy (tạm bỏ qua đồng bộ)",
    "shortcut.switchCurrent": "Chuyển nhanh qua lại giữa các máy ở màn hình lớn",
    "shortcut.switchCurrentAction": "Phím mũi tên Trái / Phải",
    "shortcut.closeCurrent": "Đóng màn hình điều khiển lớn",
    "shortcut.closeCurrentAction": "Nhấp chuột phải ra ngoài vùng trống",
    "shortcut.closeOrOpenCurrentDevice": "Mở / Đóng màn hình lớn",
    "shortcut.forcePaste": "Dán nhanh văn bản từ Mac vào iPhone",
    "shortcut.quickReply": "Mở bảng văn bản mẫu gõ nhanh",
    "shortcut.quickView": "Tìm nhanh đến ô điện thoại",
    "shortcut.quickViewAction": "Gõ số thứ tự máy",
    "shortcut.openSetting": "Mở bảng Cài đặt",
    "shortcut.adjustSize": "Chỉnh nhanh cỡ ô màn hình nhỏ",
    "shortcut.adjustQuality": "Chỉnh nhanh cỡ màn hình & độ nét",
    "shortcut.bigControl": "Khi đang mở màn hình lớn",
    "shortcut.currentTask": "Mở trình Đa nhiệm (App Switcher)",
    "shortcut.currentTaskAction": "Nhấn giữ chuột phải",
    "shortcut.backHome": "Về màn hình chính (Nút Home)",
    "shortcut.backHomeAction": "Nhấp nút cuộn giữa chuột",
    "shortcut.backPrev": "Quay lại trang trước (Vuốt Back)",
    "shortcut.backPrevAction": "Nhấp chuột phải",
    "shortcut.backPrev2": "Quay lại trang trước (Vuốt Back)",
    "shortcut.smailControl": "Khi điều khiển trực tiếp trên lưới nhỏ",
    "shortcut.smailBoxSelect": "Quét khung chọn nhiều điện thoại",
    "shortcut.smailBoxSelectAction": "Nhấn giữ và kéo chuột trái",
    "shortcut.smailHome": "Về màn hình chính (Nút Home)",
    "shortcut.smailHomeAction": "Nhấp nút cuộn giữa chuột",
    "shortcut.smailPrev": "Quay lại trang trước (Vuốt Back)",
    "shortcut.smailSelect": "Chọn / Bỏ chọn điện thoại",
    "shortcut.smailSelectAction": "Nhấn giữ chuột trái",
    "shortcut.smailTask": "Mở trình Đa nhiệm (App Switcher)",
    "shortcut.smailTaskAction": "Nhấn giữ chuột phải",
}


def update_vi_locale():
    vi_path = os.path.join(ASSETS_DIR, "vi-VN-6258b3b5.js")
    raw = open(vi_path, "r", encoding="utf-8").read()
    eval_script = raw.replace("export{t as default};", "JSON.stringify(t);")
    tmp_js = "/tmp/parse_vi_locale.js"
    with open(tmp_js, "w", encoding="utf-8") as f:
        f.write(eval_script)
    parsed_json = subprocess.check_output(["/usr/bin/osascript", "-l", "JavaScript", tmp_js]).decode("utf-8")
    vi_obj = json.loads(parsed_json)

    def clean_inline_cjk(node):
        if isinstance(node, dict):
            if "s" in node and isinstance(node["s"], str):
                s = node["s"]
                s = s.replace("投屏助手", "Trợ lý Chiếu màn hình").replace("指令助手", "Trợ lý Phím tắt").replace("初始化", "Khởi tạo ban đầu")
                node["s"] = s
            for v in node.values():
                clean_inline_cjk(v)
        elif isinstance(node, list):
            for item in node:
                clean_inline_cjk(item)

    clean_inline_cjk(vi_obj)

    for k, val in VI_UPDATES.items():
        set_nested_ast(vi_obj, k, val)

    new_js = "const t=" + json.dumps(vi_obj, ensure_ascii=False, separators=(",", ":")) + ";export{t as default};\n"
    with open(vi_path, "w", encoding="utf-8") as f:
        f.write(new_js)
    print(f"[OK] Updated {vi_path} ({len(VI_UPDATES)} refined/added Vietnamese entries)")


def patch_file_replacements(rel_path, replacements):
    full_path = os.path.join(WEB_DIR, rel_path)
    txt = open(full_path, "r", encoding="utf-8").read()
    changed = 0
    for old, new in replacements:
        if old in txt:
            txt = txt.replace(old, new)
            changed += 1
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[OK] Patched {rel_path}: {changed}/{len(replacements)} replacements applied")
    return full_path


def verify_js_syntax(js_paths):
    """Verify every modified JS module parses cleanly with /usr/bin/osascript -l JavaScript."""
    checker_js = "/tmp/check_js_syntax_osascript.js"
    for fp in js_paths:
        src = open(fp, "r", encoding="utf-8").read()
        # Strip top-level static ES module import/export statements so Function() parses the full body
        body = re.sub(r'^(?:import\s*(?:[^"\';]+from\s*)?"[^"]+"\s*;?|\s+|/\*[^*]*\*/)+', "", src)
        body = re.sub(r';?\s*export\s*(?:\{[^}]*\}|default\s+\w+)\s*;?\s*$', "", body)
        test_code = "new Function(" + json.dumps(body) + "); 'PARSE_OK';"
        with open(checker_js, "w", encoding="utf-8") as f:
            f.write(test_code)
        out = subprocess.check_output(["/usr/bin/osascript", "-l", "JavaScript", checker_js]).decode("utf-8").strip()
        assert out == "PARSE_OK", f"Unexpected output for {fp}: {out}"
        print(f"[VERIFIED] osascript -l JavaScript parsed cleanly: {os.path.relpath(fp, WEB_DIR)}")


def main():
    update_vi_locale()
    modified_js = [os.path.join(ASSETS_DIR, "vi-VN-6258b3b5.js")]

    # 1. index.html: lang="vi-VN", Vietnamese title, and modulepreload for vi-VN-6258b3b5.js
    patch_file_replacements(
        "index.html",
        [
            ('<html lang="en">', '<html lang="vi-VN">'),
            ("<title>最好用的投屏工具</title>", "<title>Xiaowei iOS — Quản lý & Điều khiển iPhone trên macOS</title>"),
            (
                '<link rel="modulepreload" crossorigin href="/assets/vue-i18n-e71848d8.js">',
                '<link rel="modulepreload" crossorigin href="/assets/vue-i18n-e71848d8.js">\n  <link rel="modulepreload" crossorigin href="/assets/vi-VN-6258b3b5.js">',
            ),
        ],
    )
    # Deduplicate modulepreload if localize_vi.py is run multiple times
    idx_html_path = os.path.join(WEB_DIR, "index.html")
    idx_html = open(idx_html_path, "r", encoding="utf-8").read()
    dup_preload = '  <link rel="modulepreload" crossorigin href="/assets/vi-VN-6258b3b5.js">\n  <link rel="modulepreload" crossorigin href="/assets/vi-VN-6258b3b5.js">'
    while dup_preload in idx_html:
        idx_html = idx_html.replace(dup_preload, '  <link rel="modulepreload" crossorigin href="/assets/vi-VN-6258b3b5.js">')
    open(idx_html_path, "w", encoding="utf-8").write(idx_html)

    # 2. index-b5cf8194.js:
    #    - Statically import viVNResource from ./vi-VN-6258b3b5.js
    #    - Pre-register "vi-VN": viVNResource in createI18n messages & set fallbackLocale: "vi-VN"
    #    - Fix loadedLanguages=["vi-VN","zh-CN","en"] and loadLanguageAsync() so vi-VN is NEVER skipped empty
    #    - Put Tiếng Việt at top of locales[], set WECAN0A95C.lang="vi-VN", and default Naive UI to viVN/dateViVN
    idx_js_path = os.path.join(ASSETS_DIR, "index-b5cf8194.js")
    idx_js = open(idx_js_path, "r", encoding="utf-8").read()
    if 'import viVNResource from"./vi-VN-6258b3b5.js";' not in idx_js:
        idx_js = 'import viVNResource from"./vi-VN-6258b3b5.js";' + idx_js
        open(idx_js_path, "w", encoding="utf-8").write(idx_js)

    modified_js.append(
        patch_file_replacements(
            "assets/index-b5cf8194.js",
            [
                ('const defaultLang="zh-CN"', 'const defaultLang="vi-VN"'),
                ('brandCode$2=localStorage.getItem("brandCode");', 'brandCode$2=localStorage.getItem("brandCode")||"WECAN0A95C";'),
                (
                    '{message,dialog,notification}=createDiscreteApi(["message","dialog","notification","loadingBar"],{messageProviderProps:{keepAliveOnHover:!0}})',
                    '{message,dialog,notification}=createDiscreteApi(["message","dialog","notification","loadingBar"],{configProviderProps:{locale:viVN,dateLocale:dateViVN},messageProviderProps:{keepAliveOnHover:!0}})',
                ),
                (
                    'const defaultLang="vi-VN",language$1=useLocalBrand("useLanguage","")',
                    'const defaultLang="vi-VN",language$1=useLocalBrand("useLanguage","vi-VN")',
                ),
                (
                    'const i18n=createI18n({legacy:!1,locale:defaultLang,fallbackLocale:"en",messages:{"zh-CN":resource$1,en:resource},warnHtmlMessage:!1,escapeParameter:!1})',
                    'const i18n=createI18n({legacy:!1,locale:defaultLang,fallbackLocale:"vi-VN",messages:{"vi-VN":viVNResource,"zh-CN":resource$1,en:resource},warnHtmlMessage:!1,escapeParameter:!1})',
                ),
                (
                    '"../../locales/vi-VN.yml":()=>__vitePreload(()=>import("./vi-VN-6258b3b5.js"),[])',
                    '"../../locales/vi-VN.yml":()=>__vitePreload(()=>Promise.resolve().then(()=>({default:viVNResource})),void 0)',
                ),
                (
                    'loadedLanguages=[defaultLang,"en"];function setI18nLanguage(t){return i18n.global.locale.value=t,typeof document<"u"&&document.querySelector("html")?.setAttribute("lang",t),t}async function loadLanguageAsync(t){if(i18n.global.locale.value===t||loadedLanguages.includes(t))return setI18nLanguage(t);const i=await localesMap[t]();return i18n.global.setLocaleMessage(t,i.default),loadedLanguages.push(t),setI18nLanguage(t)}',
                    'loadedLanguages=["vi-VN","zh-CN","en"];function setI18nLanguage(t){return i18n.global.locale.value=t,typeof document<"u"&&document.querySelector("html")?.setAttribute("lang",t),t}async function loadLanguageAsync(t){if(!t||!localesMap[t])t=defaultLang;if(loadedLanguages.includes(t)&&Object.keys(i18n.global.getLocaleMessage(t)||{}).length>0)return setI18nLanguage(t);const i=await localesMap[t]();return i18n.global.setLocaleMessage(t,i.default),loadedLanguages.includes(t)||loadedLanguages.push(t),setI18nLanguage(t)}',
                ),
                (
                    'const locales=[{code:"zh-CN",name:"简体中文",ids:[2052,4100]}',
                    'const locales=[{code:"vi-VN",name:"Tiếng Việt",ids:[1066]},{code:"zh-CN",name:"简体中文",ids:[2052,4100]}',
                ),
                (
                    ',{code:"tl-PH",name:"Tagalog",ids:[]},{code:"vi-VN",name:"Tiếng Việt",ids:[1066]},{code:"ms-MY"',
                    ',{code:"tl-PH",name:"Tagalog",ids:[]},{code:"ms-MY"',
                ),
                ('locales[n].code||defaultLang', 'locales[n]?.code||defaultLang'),
                (
                    'WECAN0A95C:{color:{main:"#2b84dd"',
                    'WECAN0A95C:{lang:"vi-VN",color:{main:"#2b84dd"',
                ),
                (
                    'return{locale:s[language$1.value]?.locale||zhCN$1,dateLocale:s[language$1.value]?.dateLocale||dateZhCN}',
                    'return{locale:s[language$1.value]?.locale||viVN,dateLocale:s[language$1.value]?.dateLocale||dateViVN}',
                ),
                ('name:"效卫投屏",title:"效卫"', 'name:"Xiaowei iOS",title:"Xiaowei"'),
                ('name:"效卫云手机",title:"云手机"', 'name:"Xiaowei Cloud",title:"Cloud"'),
                ('name:"效卫苹果投屏外设版",title:"效卫"', 'name:"Xiaowei iOS",title:"Xiaowei"'),
                ('contactPrompt:"专家服务"', 'contactPrompt:"Hỗ trợ kỹ thuật"'),
                ('message.success("截图并保存成功"', 'message.success("Đã chụp và lưu ảnh màn hình"'),
                ('title:"小微支付"', 'title:"Thanh toán"'),
                ('typeof i=="string"?i:"复制成功"', 'typeof i=="string"?i:"Đã sao chép thành công"'),
                ('name:"全部云真机"', 'name:"Tất cả máy Cloud"'),
                ('name:"未标签云真机"', 'name:"Chưa phân nhóm"'),
                ('name:"全部云手机"', 'name:"Tất cả máy ảo Cloud"'),
                ('name:"未标签云手机"', 'name:"Chưa phân nhóm"'),
                ('||"默认分组"', '||"Nhóm mặc định"'),
                ('"支付请求处理失败"', '"Xử lý thanh toán thất bại"'),
                ('`正在获取 ${a.length} 个手机粘贴板...`', '`Đang lấy bộ nhớ tạm từ ${a.length} điện thoại...`'),
                ('"客户端配置实时预览中..."', '"Đang xem trước cấu hình giao diện..."'),
                ('"客户端配置已生效，其他用户重启生效"', '"Đã áp dụng cấu hình giao diện"'),
            ],
        )
    )

    # 3. index-dd94b11a.js: hardcoded context-menu & overlay strings
    modified_js.append(
        patch_file_replacements(
            "assets/index-dd94b11a.js",
            [
                ('name:y(()=>s.value===0?"自动投屏":"不自动投屏")', 'name:y(()=>s.value===0?"Tự động chiếu màn hình":"Tắt tự động chiếu")'),
                ('name:"横屏复位"', 'name:"Đặt lại xoay ngang"'),
                ('name:"鼠标复位"', 'name:"Đặt lại con trỏ chuột"'),
                ('name:"鼠标校准"', 'name:"Hiệu chỉnh tọa độ chuột"'),
                ('message:"请先将设备切换到竖屏模式"', 'message:"Vui lòng xoay điện thoại về màn hình dọc trước"'),
                ('name:"坐标采集"', 'name:"Lấy tọa độ điểm chạm"'),
                ('placeholder:{type:String,default:"搜索菜单"}', 'placeholder:{type:String,default:"Tìm nhanh chức năng..."}'),
                ('" 该手机正在重启中，请稍等片刻。 "', '" Điện thoại đang khởi động lại, vui lòng chờ giây lát... "'),
                ('" 该手机正在恢复出厂设置，请稍等片刻。 "', '" Điện thoại đang đặt lại cài đặt gốc, vui lòng chờ... "'),
                ('" 校准中 "', '" Đang hiệu chỉnh "'),
                ('"校准过程中不可操作，请等待校准完成。"', '"Đang hiệu chỉnh tọa độ, vui lòng chờ hoàn tất..."'),
                ('return"0 小时 0 分钟"', 'return"0 giờ 0 phút"'),
            ],
        )
    )

    # 4. index-c2d36a96.js: hardcoded control panel customization labels & tooltips
    modified_js.append(
        patch_file_replacements(
            "assets/index-c2d36a96.js",
            [
                ('name:"镜像名称"', 'name:"Tên AirPlay"'),
                ('desc:"修改镜像名称"', 'desc:"Đổi tên hiển thị AirPlay"'),
                ('name:"二维码"', 'name:"Mã QR hỗ trợ"'),
                ('name:"显示放大镜"', 'name:"Hiện kính lúp"'),
                ('name:"显示备注符",panelName:"显备注符",desc:"显示小屏右上角备注图标"', 'name:"Hiện ô ghi chú",panelName:"Ghi chú",desc:"Hiện biểu tượng ghi chú ở góc trên bên phải mỗi máy"'),
                ('name:"显示内网IP"', 'name:"Hiện địa chỉ IP"'),
                ('title:"隐藏到更多功能"', 'title:"Cất bớt vào mục Công cụ mở rộng"'),
                ('title:"点击拖拽排序"', 'title:"Giữ chuột kéo để sắp xếp vị trí"'),
                ('title:"显示在控制面板"', 'title:"Đưa ra thanh công cụ chính"'),
            ],
        )
    )

    # 5. index-cd3ba413.js: hardcoded action recorder, clipboard dialog, badges & shortcut button labels
    modified_js.append(
        patch_file_replacements(
            "assets/index-cd3ba413.js",
            [
                ('?"按下":"抬起"', '?"Nhấn phím":"Nhả phím"'),
                ('re.success("已复制")', 're.success("Đã sao chép")'),
                ('n("span",null,"只读",-1)', 'n("span",null,"Chỉ đọc",-1)'),
                ('n("span",null,"显示编号和名称",-1)', 'n("span",null,"Kèm số thứ tự & tên máy",-1)'),
                ('[z(" 复制 ")]', '[z(" Sao chép ")]'),
                ('[z(" 查看全部快捷键 ")]', '[z(" Xem tất cả phím tắt ")]'),
                ('[z(" 选择文件夹 ")]', '[z(" Chọn thư mục ")]'),
                ('" 选择时间 "', '" Chọn giờ chạy "'),
                ('+"次执行时间"', '+" - Giờ chạy"'),
                ('n("span",null,"显示备注图标",-1)', 'n("span",null,"Hiện biểu tượng ghi chú",-1)'),
                ('title:"温馨提示"', 'title:"Lưu ý"'),
                ('[z(" 确定切换 ")]', '[z(" Xác nhận chuyển ")]'),
                ('"正在重置"', '"Đang đặt lại..."'),
                ('?"已完成":"安装中"', '?"Hoàn tất":"Đang cài..."'),
                ('title:"拔掉【USB数据线】",iconText:"待拔线"', 'title:"Rút cáp USB khỏi máy",iconText:"Chờ rút cáp"'),
                (
                    'z("共"),i("span",{class:"text-$main mx-1"},[m]),z("台手机，正在恢复第"),i("span",{class:"text-$main mx-1"},[S.value]),z("台")',
                    'z("Tổng "),i("span",{class:"text-$main mx-1"},[m]),z(" máy, đang khôi phục máy thứ "),i("span",{class:"text-$main mx-1"},[S.value]),z("")',
                ),
                ('"\'微软雅黑\', serif"', '"-apple-system, BlinkMacSystemFont, sans-serif"'),
                ('text:"无障碍"', 'text:"Trợ năng"'),
                ('text:"云真机"', 'text:"Máy Cloud"'),
                ('text:"云手机"', 'text:"Ảo Cloud"'),
                ('return[{name:"加载中",data:[]}]', 'return[{name:"Đang tải...",data:[]}]'),
                ('{length:A,result:"输入内容"}', '{length:A,result:"nội dung văn bản"}'),
                ('o.renewal?"续费成功！":"购买成功！"', 'o.renewal?"Gia hạn thành công!":"Mua thành công!"'),
                ('[z("重连")]', '[z("Kết nối lại")]'),
                ('title:"原价金额"', 'title:"Giá gốc"'),
                ('title:"折扣"', 'title:"Ưu đãi"'),
                ('title:"实付金额"', 'title:"Thực trả"'),
                ('"该订单下无可退款的设备"', '"Đơn hàng này không có thiết bị được hoàn tiền"'),
                ('"请选择订单"', '"Vui lòng chọn đơn hàng"'),
                ('"请选择可续费订单"', '"Vui lòng chọn đơn hàng có thể gia hạn"'),
                ('"请选择相同机型的订单"', '"Vui lòng chọn các đơn hàng cùng dòng máy"'),
                ('"未获取到可续费实例"', '"Không tìm thấy thiết bị có thể gia hạn"'),
                ('z(" 已选择 ")', 'z(" Đã chọn ")'),
                ('z(" 个订单（支持选择多个同机型订单一起续订，享受更多折扣～） ")', 'z(" đơn hàng (có thể gộp nhiều đơn cùng dòng máy để nhận thêm ưu đãi) ")'),
                (
                    '[q.remaining_time<1?`${Math.floor(q.remaining_time*60)}分钟`:`${Number.parseInt(q.remaining_time)}时`]',
                    '[q.remaining_time<1?`${Math.floor(q.remaining_time*60)} phút`:`${Number.parseInt(q.remaining_time)} giờ`]',
                ),
                ('"请选择设备"', '"Vui lòng chọn thiết bị"'),
                ('"订单异常"', '"Lỗi đơn hàng"'),
                ('`请输入${t.t("myAccount.form.realName")}`', '`Vui lòng nhập ${t.t("myAccount.form.realName")}`'),
                ('`${h.voucher_type}天`', '`${h.voucher_type} ngày`'),
                ('`${a.voucher_type}天`', '`${a.voucher_type} ngày`'),
            ],
        )
    )

    # 6. index-4ef23d01.js: macro step action log labels & stream quality labels
    modified_js.append(
        patch_file_replacements(
            "assets/index-4ef23d01.js",
            [
                ('{wheel:"滚动",textComposition:"文本",textInput:"文本",keyboard:"键盘",touch:"触摸"}', '{wheel:"Cuộn trang",textComposition:"Nhập chữ",textInput:"Nhập chữ",keyboard:"Phím bấm",touch:"Chạm màn hình"}'),
                ('{mousedown:"触摸-按下",mousemove:"触摸-移动",mouseup:"触摸-抬起",wheelUp:"滚动-向上",wheelDown:"滚动-向下"}', '{mousedown:"Chạm xuống",mousemove:"Kéo di chuyển",mouseup:"Nhả tay",wheelUp:"Cuộn lên",wheelDown:"Cuộn xuống"}'),
                ('{0:"流畅",1:"标清",2:"高清",3:"超清"}', '{0:"Mượt",1:"Tiêu chuẩn",2:"HD",3:"Siêu nét"}'),
                (
                    '{0:{value:"流畅",ratio:.7,bitrate:100},1:{value:"标清",ratio:1.1,bitrate:300},2:{value:"高清",ratio:1.5,bitrate:600},3:{value:"超清",ratio:2.1,bitrate:1e3},4:{value:"超清",ratio:2.1,bitrate:2e3}}',
                    '{0:{value:"Mượt",ratio:.7,bitrate:100},1:{value:"Tiêu chuẩn",ratio:1.1,bitrate:300},2:{value:"HD",ratio:1.5,bitrate:600},3:{value:"Siêu nét",ratio:2.1,bitrate:1e3},4:{value:"Siêu nét",ratio:2.1,bitrate:2e3}}',
                ),
                ('msg:"执行动作中"', 'msg:"Đang chạy kịch bản"'),
                ('msg:"请稍后重试"', 'msg:"Vui lòng thử lại sau"'),
                ('`云机${o}小时后到期，请及时续费`', '`Máy Cloud sẽ hết hạn sau ${o} giờ, vui lòng gia hạn`'),
                ('`云机${c}小时后到期，请及时续费`', '`Máy Cloud sẽ hết hạn sau ${c} giờ, vui lòng gia hạn`'),
                ('`您有${t.length}台云手机退款成功！`', '`Đã hoàn tiền thành công cho ${t.length} máy Cloud!`'),
                ('O.t("上传失败")', '"Tải lên thất bại"'),
                ('`上传失败: ${t.name}`', '`Tải lên thất bại: ${t.name}`'),
                ('"上传文件到阿里云服务器失败"', '"Tải tệp lên máy chủ thất bại"'),
            ],
        )
    )

    # 7. Remaining Vue chunks: index-4e413548, OTGSetting, deviceCloud, HomeCanvas, PhoneFun, SystemDiagnose, Version
    modified_js.append(
        patch_file_replacements(
            "assets/index-4e413548.js",
            [
                (
                    'payRecordStatus:[{label:"使用中",value:0,color:"text-green-500"},{label:"已到期",value:1,color:"text-red-500"},{label:"已转移",value:2,color:"text-blue-500"},{label:"已更换",value:3,color:"text-yellow-500"},{label:"已断连",value:4,color:"text-red-500"}]',
                    'payRecordStatus:[{label:"Đang dùng",value:0,color:"text-green-500"},{label:"Đã hết hạn",value:1,color:"text-red-500"},{label:"Đã chuyển",value:2,color:"text-blue-500"},{label:"Đã đổi máy",value:3,color:"text-yellow-500"},{label:"Mất kết nối",value:4,color:"text-red-500"}]',
                ),
                ('"支付页未返回订单或激活码"', '"Trang thanh toán chưa trả về đơn hàng hoặc mã kích hoạt"'),
            ],
        )
    )
    modified_js.append(
        patch_file_replacements(
            "assets/OTGSetting-f816ce3a.js",
            [
                ('"抱歉，扫描的范围不能超过500，请减少扫描ip数量后重试！"', '"Phạm vi quét không được vượt quá 500 địa chỉ IP, vui lòng giảm phạm vi và thử lại!"'),
            ],
        )
    )
    modified_js.append(
        patch_file_replacements(
            "assets/deviceCloud-6b3a38a0.js",
            [
                ('`云机${v}小时后到期，请及时续费`', '`Máy Cloud sẽ hết hạn sau ${v} giờ, vui lòng gia hạn`'),
            ],
        )
    )
    modified_js.append(
        patch_file_replacements(
            "assets/HomeCanvas.vue_vue_type_script_setup_true_lang-38757236.js",
            [
                ('"16px 微软雅黑"', '"16px -apple-system, BlinkMacSystemFont, sans-serif"'),
            ],
        )
    )
    modified_js.append(
        patch_file_replacements(
            "assets/PhoneFun-4a458a53.js",
            [
                ('`重置为系统默认(${t(E)}s)`:"重置为系统默认"', '`Khôi phục bố cục mặc định (${t(E)}s)`:"Khôi phục bố cục mặc định"'),
            ],
        )
    )
    modified_js.append(
        patch_file_replacements(
            "assets/SystemDiagnose-b2b70b5f.js",
            [
                ('placeholder:"请输入手机序列号"', 'placeholder:"Tìm theo tên hoặc mã UDID điện thoại..."'),
                ('?"云机列表":', '?"Danh sách máy Cloud":'),
            ],
        )
    )
    modified_js.append(
        patch_file_replacements(
            "assets/Version-9821da92.js",
            [
                ('z.success("复制成功")', 'z.success("Đã sao chép thành công")'),
            ],
        )
    )

    verify_js_syntax(modified_js)


if __name__ == "__main__":
    main()
