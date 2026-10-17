using System.Text;
using System.Text.Json;
using ClassIsland.Core.Abstractions.Services;
using ClassIsland.Shared.Enums;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace ClassDesktopManagerBridge;

/// <summary>
/// 把 ClassIsland 当前课程状态写到 %APPDATA%\classDesktopManager\classisland.json，
/// 供 classDesktopManager 读取，用于按当前课程辅助文件分类。
/// </summary>
public sealed class LessonBridgeService : IHostedService, IDisposable
{
    private const int SchemaVersion = 1;

    private readonly ILessonsService _lessons;
    private readonly ILogger<LessonBridgeService> _logger;
    private readonly string _outputPath;
    private readonly object _writeLock = new();
    private Timer? _heartbeat;

    public LessonBridgeService(ILessonsService lessons, ILogger<LessonBridgeService> logger)
    {
        _lessons = lessons;
        _logger = logger;

        var dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "classDesktopManager");
        Directory.CreateDirectory(dir);
        _outputPath = Path.Combine(dir, "classisland.json");
    }

    public Task StartAsync(CancellationToken cancellationToken)
    {
        _lessons.OnClass += OnLessonChanged;
        _lessons.OnBreakingTime += OnLessonChanged;
        _lessons.OnAfterSchool += OnLessonChanged;
        _lessons.CurrentTimeStateChanged += OnLessonChanged;

        WriteSnapshot("start");
        _heartbeat = new Timer(_ => WriteSnapshot("heartbeat"), null,
            TimeSpan.FromSeconds(10), TimeSpan.FromSeconds(10));
        _logger.LogInformation("classDesktopManager bridge 已启动，输出：{Path}", _outputPath);
        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken cancellationToken)
    {
        _lessons.OnClass -= OnLessonChanged;
        _lessons.OnBreakingTime -= OnLessonChanged;
        _lessons.OnAfterSchool -= OnLessonChanged;
        _lessons.CurrentTimeStateChanged -= OnLessonChanged;

        _heartbeat?.Dispose();
        _heartbeat = null;
        WriteSnapshot("stop");
        return Task.CompletedTask;
    }

    public void Dispose()
    {
        _heartbeat?.Dispose();
    }

    private void OnLessonChanged(object? sender, EventArgs e) => WriteSnapshot("event");

    private void WriteSnapshot(string trigger)
    {
        try
        {
            var subject = _lessons.CurrentSubject;
            var subjectName = IsUsableSubject(subject) ? subject!.Name : null;
            var state = _lessons.CurrentState;

            var payload = new
            {
                schema = SchemaVersion,
                source = "ClassIsland",
                trigger,
                updated = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                state = state.ToString(),
                onClass = state == TimeState.OnClass && _lessons.IsTimerRunning,
                subject = subjectName,
                nextSubject = IsUsableSubject(_lessons.NextClassSubject)
                    ? _lessons.NextClassSubject!.Name
                    : null,
                lessonConfirmed = _lessons.IsLessonConfirmed,
                classPlanEnabled = _lessons.IsClassPlanEnabled,
                classPlanLoaded = _lessons.IsClassPlanLoaded,
            };

            var json = JsonSerializer.Serialize(payload,
                new JsonSerializerOptions { WriteIndented = true });

            lock (_writeLock)
            {
                var tmp = _outputPath + ".tmp";
                File.WriteAllText(tmp, json, new UTF8Encoding(false));
                File.Move(tmp, _outputPath, true);
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "写入课程状态失败");
        }
    }

    private static bool IsUsableSubject(ClassIsland.Shared.Models.Profile.Subject? subject)
    {
        if (subject is null)
        {
            return false;
        }

        var name = subject.Name;
        if (string.IsNullOrWhiteSpace(name))
        {
            return false;
        }

        return name != "???" && name != "课间休息" && name != "放学";
    }
}
