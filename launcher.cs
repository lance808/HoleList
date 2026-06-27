using System;
using System.Diagnostics;
using System.IO;

class Launcher
{
    static void Main()
    {
        string dir = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
        string mainPy = Path.Combine(dir, "main.py");

        string[] pythons = { "python", "python3", "py" };
        foreach (string python in pythons)
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = python,
                    Arguments = "\"" + mainPy + "\"",
                    WorkingDirectory = dir,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                };
                Process.Start(psi).WaitForExit();
                return;
            }
            catch (Exception)
            {
                continue;
            }
        }
    }
}