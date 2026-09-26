// Does the PRODUCT APP put each MIC's gain byte where the hardware reads it?
//
// This runs the app's OWN code -- AnalogControlChain.BuildImage and ToWire,
// loaded out of the built assembly by reflection -- rather than re-deriving
// what it ought to do. For each panel channel 1..24 it builds an image in
// which that channel alone carries a recognisable gain code and every other
// channel is at minimum, converts it to wire order exactly as the app does
// before it clocks it, and reports which transmit byte the marked value
// landed in. That byte index is then compared with defs' send_pos and with
// the position S125 measured on MW-D24-2.
using System;
using System.Collections;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;

class P
{
    static string Dir = "/home/peter/mx26/src/sw/app/bin/Release/net10.0";

    static int Main()
    {
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) =>
        {
            string n = new AssemblyName(e.Name).Name + ".dll";
            string p = Path.Combine(Dir, n);
            return File.Exists(p) ? Assembly.LoadFrom(p) : null;
        };
        var asm = Assembly.LoadFrom(Path.Combine(Dir, "app.dll"));
        var acc = asm.GetType("app_avalonia.Core.AnalogControlChain");
        var st = asm.GetType("app_avalonia.Core.AnalogChannelState");
        var lay = asm.GetType("app_avalonia.Core.ChainLayout");
        var imap = asm.GetType("app_avalonia.Core.InputMap");

        // The layout the app would actually use, and where it came from.
        var def = lay.GetProperty("Default", BindingFlags.Public | BindingFlags.Static).GetValue(null);
        Console.WriteLine("Default layout source: " + lay.GetProperty("Source").GetValue(def));

        // AND THE DEFS-DERIVED LAYOUT, explicitly. On a machine with a defs
        // checkout the app builds images with this one; on a deployed unit it
        // falls back to the compiled table. Both are exercised here, because
        // "the app is right" has to mean both.
        object fromDefs = null;
        {
            var tryParse = imap.GetMethod("TryParse", BindingFlags.Public | BindingFlags.Static);
            object[] argsP = new object[] { File.ReadAllText("/home/peter/dsp/defs/products/d24/inputs.csv"), null, null };
            bool okP = (bool)tryParse.Invoke(null, argsP);
            Console.WriteLine("InputMap.TryParse(defs inputs.csv): " + okP + " " + argsP[2]);
            if (!okP) return 3;
            var fromMap = lay.GetMethod("FromInputMap", BindingFlags.Public | BindingFlags.Static);
            fromDefs = fromMap.Invoke(null, new object[] { argsP[1] });
            Console.WriteLine("defs layout source:    " + lay.GetProperty("Source").GetValue(fromDefs));
        }

        // defs' own send_pos, read straight out of the CSV.
        var sendPos = new System.Collections.Generic.Dictionary<int, int>();
        var chainIx = new System.Collections.Generic.Dictionary<int, int>();
        string csv = "/home/peter/dsp/defs/products/d24/inputs.csv";
        string[] hdr = null;
        foreach (var line in File.ReadAllLines(csv))
        {
            var t = line.Trim();
            if (t.Length == 0 || t.StartsWith("#")) continue;
            var parts = t.Split(',');
            if (hdr == null) { hdr = parts; continue; }
            string panel = parts[Array.IndexOf(hdr, "panel")].Trim();
            if (!panel.StartsWith("MIC ")) continue;
            int n = int.Parse(new string(panel.Where(char.IsDigit).ToArray()));
            sendPos[n] = int.Parse(parts[Array.IndexOf(hdr, "send_pos")].Trim());
            chainIx[n] = int.Parse(parts[Array.IndexOf(hdr, "chain_index")].Trim());
        }

        // S125's measurement: tx byte (0-based) -> converter lane.
        var measured = new System.Collections.Generic.Dictionary<int, int>
        {
            {0,24},{1,12},{2,23},{3,11},{4,22},{5,10},{6,21},{7,9},
            {8,20},{9,8},{10,19},{11,7},{12,18},{13,6},{14,17},{15,5}
        };

        var buildImage = acc.GetMethod("BuildImage", BindingFlags.Public | BindingFlags.Static);
        var toWire = acc.GetMethod("ToWire", BindingFlags.Public | BindingFlags.Static);
        var safeProp = st.GetProperty("Safe", BindingFlags.Public | BindingFlags.Static);
        object safe = safeProp.GetValue(null);

        // A channel state with a gain the safe state does not use, so the byte
        // it produces is unmistakable in the image.
        var ctor = st.GetConstructors().OrderByDescending(c => c.GetParameters().Length).First();
        Console.WriteLine("AnalogChannelState ctor: (" + string.Join(", ",
            ctor.GetParameters().Select(x => x.ParameterType.Name + " " + x.Name)) + ")");

        Console.WriteLine();
        Console.WriteLine("MIC  chain_index  defs send_pos  app tx (fallback)  app tx (defs)  measured  verdict");
        int bad = 0, checkedRows = 0;
        for (int mic = 1; mic <= 24; mic++)
        {
            var arr = Array.CreateInstance(st, 24);
            for (int i = 0; i < 24; i++) arr.SetValue(safe, i);
            object marked = MarkedState(st, ctor, safe);
            arr.SetValue(marked, mic - 1);
            byte markByte = ChannelByte(acc, marked);
            byte safeByte = ChannelByte(acc, safe);
            if (markByte == safeByte) { Console.WriteLine("cannot mark a channel distinctly"); return 2; }

            int[] Where(object layout)
            {
                byte[] image = (byte[])buildImage.Invoke(null, new object[] { arr, false, false, layout });
                byte[] wire = (byte[])toWire.Invoke(null, new object[] { image });
                return Enumerable.Range(0, wire.Length).Where(i => wire[i] == markByte).ToArray();
            }
            var atF = Where(null);
            var atD = Where(fromDefs);
            string txF = atF.Length == 1 ? atF[0].ToString() : "[" + string.Join(",", atF) + "]";
            string txD = atD.Length == 1 ? atD[0].ToString() : "[" + string.Join(",", atD) + "]";
            int m = measured.TryGetValue(sendPos[mic], out int lane) ? lane : -1;
            string meas = m < 0 ? "depop" : (m == mic ? sendPos[mic].ToString() : "lane " + m + "!");
            bool ok = atF.Length == 1 && atD.Length == 1
                      && atF[0] == sendPos[mic] && atD[0] == sendPos[mic] && (m < 0 || m == mic);
            if (m >= 0) { checkedRows++; if (!ok) bad++; }
            Console.WriteLine($"{mic,3}  {chainIx[mic],11}  {sendPos[mic],13}  {txF,17}  {txD,13}  {meas,8}  {(ok ? "OK" : "MISMATCH")}");
        }
        Console.WriteLine();
        Console.WriteLine($"{checkedRows} populated inputs checked against the part, {bad} disagree");
        return bad == 0 ? 0 : 1;
    }

    static object MarkedState(Type st, ConstructorInfo ctor, object safe)
    {
        // Build a state with a gain code the safe state does not carry.
        var ps = ctor.GetParameters();
        var args = new object[ps.Length];
        for (int i = 0; i < ps.Length; i++)
        {
            var pi = ps[i];
            object cur = st.GetProperties().FirstOrDefault(x =>
                string.Equals(x.Name, pi.Name, StringComparison.OrdinalIgnoreCase))?.GetValue(safe);
            if (pi.Name.ToLowerInvariant().Contains("gain"))
                args[i] = Convert.ChangeType(21, pi.ParameterType);   // 0b010101, unmistakable
            else if (cur != null && pi.ParameterType.IsInstanceOfType(cur)) args[i] = cur;
            else args[i] = pi.ParameterType.IsValueType ? Activator.CreateInstance(pi.ParameterType) : null;
        }
        return ctor.Invoke(args);
    }

    static byte ChannelByte(Type acc, object state)
    {
        var m = acc.GetMethod("ChannelByte", BindingFlags.Public | BindingFlags.Static | BindingFlags.NonPublic);
        return (byte)m.Invoke(null, new object[] { state });
    }
}
