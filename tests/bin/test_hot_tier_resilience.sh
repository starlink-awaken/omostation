#!/bin/bash
# test_hot_tier_resilience.sh — bin/ops/hot-tier-resilience.sh 的回归测试 (BET-Y2Q4-T10-243)
#
# 覆盖的是 2026-10-11/12 实测出的静默假通过与排程缺口, 每条断言都对应一个真实踩过的坑:
#   · verify 对平铺模型目录/读不到的热层/抽样为 0 判"一致" → 必须判失败
#   · manifest 在读不到热层时把 Lex 上好的旧清单覆盖成空壳 → 必须保留旧清单
#   · launchd 直启读不了外接卷 (TCC) → 卷预检要返回 77 而不是放行后 rsync 才失败
#   · daily-report 在 0 命中时折行; 周任务心跳/补跑; install-schedule 只生成不安装
#
# 全部在临时目录里用环境变量覆盖路径, 不碰真实卷、不碰 launchd、不发桌面通知。
# macOS 专用 (stat -f / date -v / plutil): 其它系统直接跳过 —— CI 的 ubuntu 上这条是"跳过"而不是"通过"。
set -uo pipefail

if [ "$(uname)" != "Darwin" ]; then
    echo "SKIP: hot-tier-resilience.sh 依赖 macOS 工具 (stat -f / date -v / plutil), 本平台跳过"
    exit 0
fi

# HOT_TIER_SCRIPT 仅用于变异检查: 拿旧版本跑一遍, 确认这些断言真的会红
SCRIPT="${HOT_TIER_SCRIPT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/bin/ops/hot-tier-resilience.sh}"
[ -f "$SCRIPT" ] || { echo "❌ 找不到 $SCRIPT"; exit 1; }

FAILS=0
T=""
ok()  { printf '  ✅ %s\n' "$1"; }
bad() { printf '  ❌ %s\n' "$1"; FAILS=$((FAILS + 1)); }
check() {  # check <描述> <命令...>: 命令成功即通过
    local desc="$1"; shift
    if "$@" >/dev/null 2>&1; then ok "$desc"; else bad "$desc"; fi
}
expect_rc() {  # expect_rc <描述> <期望退出码> <实际退出码>
    if [ "$2" -eq "$3" ]; then ok "$1 (rc=$3)"; else bad "$1: 期望 rc=$2, 实际 rc=$3"; fi
}
# shellcheck disable=SC2329  # 经 check 间接调用
contains() {  # contains <文本> <子串>
    case "$1" in *"$2"*) return 0 ;; *) return 1 ;; esac
}

cleanup() { [ -n "$T" ] && { chmod -R u+rwx "$T" 2>/dev/null; rm -rf "$T"; }; }
trap cleanup EXIT

# 每个用例一套全新夹具: 稀有发布者 acme-lab (嵌套模型) + 平铺模型 flat-embed-model + 公开源 mlx-community
new_fixture() {
    cleanup
    T=$(mktemp -d "${TMPDIR:-/tmp}/htr-test.XXXXXX")
    HOT="$T/hot/lmstudio"; LEX="$T/lex/cold-backup/sharemodel-hot-tier"
    mkdir -p "$HOT/acme-lab/model-a" "$HOT/flat-embed-model" "$HOT/mlx-community/pub-1" "$T/omlx/models-active" "$T/bin" "$T/ws"
    echo '{"k":1}' > "$HOT/acme-lab/model-a/config.json"
    head -c 4096 /dev/zero > "$HOT/acme-lab/model-a/weights.bin"
    echo '{"flat":1}' > "$HOT/flat-embed-model/config.json"
    head -c 1024 /dev/zero > "$HOT/flat-embed-model/model.bin"
    echo x > "$HOT/mlx-community/pub-1/config.json"
    ln -s "$HOT/acme-lab/model-a" "$T/omlx/models-active/model-a"
    printf '#!/bin/bash\necho "$@" >> "%s/open.log"\n' "$T" > "$T/bin/open-stub.sh"; chmod 755 "$T/bin/open-stub.sh"
    : > "$T/keepalive.log"; : > "$T/keepalive.drops"; : > "$T/keepalive.daily"
}

run() {  # run <子命令...>: 在夹具里跑脚本; 输出存 $OUT, 退出码存 $RC
    OUT=$(env HOME="$T/home" HOT_TIER_HOT="$HOT" HOT_TIER_LEX="$LEX" HOT_TIER_OMLX="$T/omlx" HOT_TIER_WS="$T/ws" \
        HOT_TIER_STATE="$T/state" HOT_TIER_LOG="$T/weekly.log" HOT_TIER_NO_NOTIFY=1 \
        HOT_TIER_OPEN_CMD="$T/bin/open-stub.sh" HOT_TIER_LAUNCHER="$T/libexec/weekly.command" HOT_TIER_STAGE="$T/stage" \
        HOT_TIER_INSTALL_SELF="/stable/ws/bin/ops/hot-tier-resilience.sh" \
        KEEPALIVE_LOG="$T/keepalive.log" KEEPALIVE_STATE="$T/keepalive.state" KEEPALIVE_DAILY="$T/keepalive.daily" \
        KEEPALIVE_DROPS="$T/keepalive.drops" /bin/bash "$SCRIPT" "$@" 2>&1)
    RC=$?
}

can_chmod_block() { [ "$(id -u)" -ne 0 ]; }  # root 不受 chmod 000 限制, 相关用例跳过

echo "== 1. 正常链路: sync-rare → manifest → verify"
new_fixture
run sync-rare;  expect_rc "sync-rare 成功" 0 $RC
check "sync-rare 记了 last-sync-rare.ok" test -f "$T/state/last-sync-rare.ok"
run manifest;   expect_rc "manifest 成功" 0 $RC
check "Lex 上有重建清单且含公开源条目" grep -q '^- pub-1' "$LEX/PUBLIC-MODELS-REBUILD-MANIFEST.md"
check "仓内副本同步写出" grep -q '^- pub-1' "$T/ws/docs/generated/public-models-manifest.md"
run verify;     expect_rc "verify 通过" 0 $RC
check "verify 报告 抽样>0 且 不一致 0" contains "$OUT" "不一致 0"
check "verify 记了 last-verify.ok" test -f "$T/state/last-verify.ok"

echo "== 2. verify 必须抓得到差异 (含 10-11 修掉的平铺目录假通过)"
new_fixture; run sync-rare >/dev/null; run manifest >/dev/null
head -c 9 /dev/zero >> "$LEX/rare-publishers/acme-lab/model-a/weights.bin"
run verify;     expect_rc "嵌套模型文件大小不同 → 失败" 1 $RC
check "报出 MISMATCH: acme-lab/model-a" contains "$OUT" "MISMATCH: acme-lab/model-a"
new_fixture; run sync-rare >/dev/null; run manifest >/dev/null
rm -rf "$LEX/rare-publishers/flat-embed-model"
run verify;     expect_rc "平铺模型在 Lex 缺失 → 失败 (曾被静默判一致)" 1 $RC
check "报出 MISMATCH: flat-embed-model" contains "$OUT" "MISMATCH: flat-embed-model"

echo "== 3. verify 不能在什么都没校验时通过"
new_fixture; run sync-rare >/dev/null; run manifest >/dev/null
rm -rf "$HOT/acme-lab" "$HOT/flat-embed-model"
run verify;     expect_rc "热层没有稀有发布者 → 抽样为 0 → 失败" 1 $RC
check "说明原因是抽样为 0" contains "$OUT" "抽样为 0"
new_fixture; run sync-rare >/dev/null; run manifest >/dev/null
touch -t 202001010000 "$LEX/PUBLIC-MODELS-REBUILD-MANIFEST.md"
run verify;     expect_rc "清单超过 7 天 → 失败" 1 $RC
check "说明清单超期" contains "$OUT" "超过 RPO 承诺"

echo "== 4. 读不到热层 (模拟 TCC/权限被拒): 卷预检返回 77, 且不破坏旧清单"
if can_chmod_block; then
    new_fixture; run sync-rare >/dev/null; run manifest >/dev/null
    echo GOOD-OLD-MANIFEST > "$LEX/PUBLIC-MODELS-REBUILD-MANIFEST.md"
    chmod 000 "$HOT"
    run verify;     expect_rc "verify: 热层读不了 → 77 (而不是 exit 0)" 77 $RC
    run manifest;   expect_rc "manifest: 热层读不了 → 77" 77 $RC
    run sync-rare;  expect_rc "sync-rare: 热层读不了 → 77" 77 $RC
    chmod 755 "$HOT"
    check "Lex 上的旧清单没被冲掉" grep -q GOOD-OLD-MANIFEST "$LEX/PUBLIC-MODELS-REBUILD-MANIFEST.md"
    # 守卫放行但目录里没有公开源条目 (空读) 时, manifest 也不能覆盖
    new_fixture; run sync-rare >/dev/null
    echo GOOD-OLD-MANIFEST > "$LEX/PUBLIC-MODELS-REBUILD-MANIFEST.md"
    rm -rf "$HOT/mlx-community"
    run manifest;   expect_rc "manifest: 公开源目录全空 → 失败" 1 $RC
    check "空清单没有覆盖旧清单" grep -q GOOD-OLD-MANIFEST "$LEX/PUBLIC-MODELS-REBUILD-MANIFEST.md"
else
    echo "  (以 root 运行, chmod 000 拦不住, 跳过本节)"
fi

echo "== 5. 周任务 weekly: 成功记 OK, 失败停在出错的那一步并记 FAIL"
new_fixture
run weekly;     expect_rc "weekly 全部通过" 0 $RC
check "last-weekly.status 以 OK 开头" grep -q '^OK ' "$T/state/last-weekly.status"
check "记了整链成功戳 last-weekly.ok" test -f "$T/state/last-weekly.ok"
if can_chmod_block; then
    new_fixture
    mkdir -p "$T/lex"; chmod 555 "$T/lex"
    run weekly;     expect_rc "Lex 不可写 → weekly 以 77 失败" 77 $RC
    check "状态记为 FAIL sync-rare 77" grep -q '^FAIL sync-rare 77 ' "$T/state/last-weekly.status"
    check "没有记整链成功戳" test ! -f "$T/state/last-weekly.ok"
    chmod 755 "$T/lex"
fi

echo "== 6. daily-report: 不折行、带真实掉线、带周任务心跳"
new_fixture
run daily-report 2026-10-13;   expect_rc "daily-report 成功" 0 $RC
check "0 命中日只追加 2 行 (日报 + 心跳), 没有折行" test "$(grep -c '^\[' "$T/keepalive.daily")" -eq 2
check "第一行真实掉线=0" grep -q '真实掉线=0 ' "$T/keepalive.daily"
check "没有周任务成功记录 → 心跳写明从未整链成功" grep -q '周任务心跳: 从未整链成功' "$T/keepalive.daily"
echo "2026-10-13 12:00:00 REAL_DROP DK5A1 ss_removed=3" > "$T/keepalive.drops"
: > "$T/keepalive.daily"
run daily-report 2026-10-13
check "真实掉线=1 且带同刻消失设备数" grep -q '真实掉线=1 (同刻消失SS设备数: 3)' "$T/keepalive.daily"
echo "== 6b. 心跳新鲜时不告警、不补跑"
new_fixture; run weekly >/dev/null; : > "$T/keepalive.daily"
run daily-report 2026-10-13
check "心跳显示 上次整链成功 0d 前" grep -q '上次整链成功 0d 前' "$T/keepalive.daily"
check "新鲜心跳不触发补跑" test ! -f "$T/open.log"

echo "== 7. 周任务超期 → 补跑: 经终端 App 拉起启动器, 且 20 小时内不重复"
new_fixture
mkdir -p "$T/state" "$T/libexec"; printf '#!/bin/bash\nexit 0\n' > "$T/libexec/weekly.command"; chmod 755 "$T/libexec/weekly.command"
echo "$(( $(date +%s) - 20 * 86400 )) old" > "$T/state/last-weekly.ok"
run daily-report 2026-10-13
check "心跳写明超过 8d" grep -q '超过 8d' "$T/keepalive.daily"
check "补跑: open -g -j -a iTerm <启动器>" grep -q -- "-g -j -a iTerm $T/libexec/weekly.command" "$T/open.log"
rm -f "$T/open.log"; printf 'RUNNING - 0 %s\n' "$(date +%s)" > "$T/state/last-weekly.status"
run daily-report 2026-10-13
check "20 小时内已尝试过 → 不再补跑" test ! -f "$T/open.log"
rm -f "$T/open.log" "$T/state/last-weekly.status"; rm -f "$T/libexec/weekly.command"
run daily-report 2026-10-13
check "启动器不存在 → 跳过并提示先 install-schedule" contains "$OUT" "先 install-schedule"

echo "== 8. probe: 把 TCC 类失败分成 77 (被拒) 与 75 (不在线)"
new_fixture
run probe "$T/probe.out" t1;    expect_rc "probe 执行" 0 $RC
check "热层可读、Lex 可写 → hot=0 lex_write=0" grep -q 'hot=0 lex_write=0' "$T/probe.out"
if can_chmod_block; then
    chmod 000 "$HOT"; rm -f "$T/probe.out"
    run probe "$T/probe.out" t2
    chmod 755 "$HOT"
    check "热层被拒 → hot=77" grep -q 'hot=77' "$T/probe.out"
    mkdir -p "$T/lex"; chmod 555 "$T/lex"; rm -f "$T/probe.out"
    run probe "$T/probe.out" t3
    chmod 755 "$T/lex"
    check "Lex 被拒 → lex_write=77" grep -q 'lex_write=77' "$T/probe.out"
fi

echo "== 9. install-schedule: 只生成, 不安装"
new_fixture; mkdir -p "$T/home/Library/LaunchAgents"
run install-schedule;           expect_rc "install-schedule 成功" 0 $RC
check "plist 通过 plutil -lint" plutil -lint "$T/stage/com.local.hot-tier-resilience.plist"
check "plist 经 open -a iTerm 拉启动器" grep -q "<string>$T/libexec/weekly.command</string>" "$T/stage/com.local.hot-tier-resilience.plist"
check "plist 用 /usr/bin/open" grep -q '<string>/usr/bin/open</string>\|<string>'"$T"'/bin/open-stub.sh</string>' "$T/stage/com.local.hot-tier-resilience.plist"
check "排程是周日 04:00" grep -q '<key>Weekday</key><integer>0</integer><key>Hour</key><integer>4</integer>' "$T/stage/com.local.hot-tier-resilience.plist"
check "启动器指向稳定路径并跑 weekly" grep -q '/stable/ws/bin/ops/hot-tier-resilience.sh" weekly' "$T/stage/hot-tier-weekly.command"
check "启动器可执行" test -x "$T/stage/hot-tier-weekly.command"
check "打印了手动安装命令" contains "$OUT" "launchctl bootstrap"
check "没有往 LaunchAgents 里放任何东西" test -z "$(ls -A "$T/home/Library/LaunchAgents")"
check "没有创建真实启动器路径" test ! -e "$T/libexec/weekly.command"
OUT=$(env HOME="$T/home" HOT_TIER_STAGE="$T/stage2" HOT_TIER_LAUNCH_MODE=direct HOT_TIER_INSTALL_SELF=/stable/x.sh /bin/bash "$SCRIPT" install-schedule 2>&1)
check "direct 模式 plist 直接跑 /bin/bash" grep -q '<string>/bin/bash</string>' "$T/stage2/com.local.hot-tier-resilience.plist"

echo "== 10. 用法"
new_fixture
run;                            expect_rc "无参数 → 打印用法, rc=64" 64 $RC
check "用法里列出 selftest-launchd" contains "$OUT" "selftest-launchd"

echo
if [ "$FAILS" -eq 0 ]; then echo "✅ hot-tier-resilience 全部用例通过"; exit 0; fi
echo "❌ $FAILS 个断言失败"; exit 1
