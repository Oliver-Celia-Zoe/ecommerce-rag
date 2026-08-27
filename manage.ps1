# ==========================================
# Air Fryer AI Assistant - Windows PowerShell 一键脚本
# ==========================================
# 用法：
#   .\manage.ps1 dev         启动开发环境（前台，看日志）
#   .\manage.ps1 dev -d       启动开发环境（后台）
#   .\manage.ps1 dev -build  重建镜像并启动
#   .\manage.ps1 prod        启动生产环境（需先配 .env.prod）
#   .\manage.ps1 down        停止当前环境
#   .\manage.ps1 logs        查看日志
#   .\manage.ps1 ps         查看容器状态
#   .\manage.ps1 clean      停止并删除卷（慎用）
#
# 首次运行如报错"无法加载脚本"，执行一次：
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

param(
    [Parameter(Position=0)]
    [ValidateSet("dev","prod","down","logs","ps","clean","help")]
    [string]$Action = "help",

    [switch]$d,           # 后台运行
    [switch]$build        # 重建镜像
)

$DevCompose = @("-f","docker-compose.yml","-f","docker-compose.dev.yml")
$ProdCompose = @("--env-file",".env.prod","-f","docker-compose.yml","-f","docker-compose.prod.yml")

switch ($Action) {
    "dev" {
        $cmd = @("docker","compose") + $DevCompose + @("up")
        if ($d) { $cmd += "-d" }
        if ($build) { $cmd += "--build" }
        Write-Host "启动开发环境..." -ForegroundColor Cyan
        & $cmd[0] $cmd[1..($cmd.Length-1)]
    }
    "prod" {
        if (-not (Test-Path ".env.prod")) {
            Write-Host "错误：请先创建 .env.prod（参考 .env.prod.example）" -ForegroundColor Red
            exit 1
        }
        $cmd = @("docker","compose") + $ProdCompose + @("up","-d")
        if ($build) { $cmd += "--build" }
        Write-Host "启动生产环境..." -ForegroundColor Cyan
        & $cmd[0] $cmd[1..($cmd.Length-1)]
    }
    "down" {
        Write-Host "停止服务..." -ForegroundColor Cyan
        docker compose @DevCompose down 2>$null
        docker compose @ProdCompose down 2>$null
    }
    "logs" {
        docker compose @DevCompose logs -f
    }
    "ps" {
        docker compose @DevCompose ps
    }
    "clean" {
        $confirm = Read-Host "将停止所有服务并删除数据卷（数据会丢失）！确认？(y/N)"
        if ($confirm -eq "y") {
            docker compose @DevCompose down -v
            docker compose @ProdCompose down -v
            Write-Host "已清理" -ForegroundColor Green
        }
    }
    "help" {
        Write-Host "Air Fryer AI Assistant - Docker 命令" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "开发环境："
        Write-Host "  .\manage.ps1 dev          启动（前台，看日志）"
        Write-Host "  .\manage.ps1 dev -d        启动（后台）"
        Write-Host "  .\manage.ps1 dev -build   重建镜像并启动"
        Write-Host "  .\manage.ps1 down         停止"
        Write-Host ""
        Write-Host "生产环境："
        Write-Host "  .\manage.ps1 prod         启动（需先配 .env.prod）"
        Write-Host "  .\manage.ps1 prod -build  重建镜像并启动"
        Write-Host ""
        Write-Host "工具："
        Write-Host "  .\manage.ps1 logs         查看日志"
        Write-Host "  .\manage.ps1 ps           查看容器"
        Write-Host "  .\manage.ps1 clean        停止并删除卷（慎用！）"
    }
}
