import os
import sys
sys.path.append(os.path.dirname(__file__))
from agri_opt.data_model import DATA

locations = sorted(DATA['location_names'])
options_html = "<option value=''>-- Select Point --</option>" + "".join([f"<option value='{loc}'>{loc}</option>" for loc in locations])

html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Logistics Optimization Comparison</title>
    <style>
        body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; flex-direction: column; height: 100vh; overflow: hidden; background: #f0f2f5; }}
        .header {{ background: #fff; padding: 15px 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; z-index: 100; }}
        .header h2 {{ margin: 0; font-size: 1.2rem; color: #1a1a1a; }}
        .controls {{ display: flex; gap: 15px; align-items: center; }}
        select, button {{ padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px; outline: none; cursor: pointer; }}
        button {{ background: #007bff; color: white; border: none; font-weight: bold; }}
        button.reset {{ background: #6c757d; }}
        button:hover {{ opacity: 0.9; }}
        .content {{ flex: 1; display: flex; flex-direction: row; position: relative; }}
        .frame-container {{ flex: 1; position: relative; display: flex; flex-direction: column; border-right: 2px solid #ccc; }}
        .frame-container:last-child {{ border-right: none; }}
        .frame-title {{ position: absolute; top: 10px; right: 10px; background: rgba(255,255,255,0.9); padding: 5px 10px; border-radius: 4px; font-weight: bold; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); pointer-events: none; z-index: 10; }}
        iframe {{ width: 100%; height: 100%; border: none; }}
        
        /* Master UI Panel */
        .master-ui {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
            background: #f8f9fa;
            padding: 10px 15px;
            border-radius: 8px;
            border: 1px solid #dee2e6;
        }}
        .master-ui label {{ font-weight: 500; font-size: 14px; }}
        @media (max-width: 1000px) {{
            .header {{ flex-direction: column; align-items: stretch; gap: 10px; }}
            .master-ui {{ justify-content: center; }}
            .controls {{ justify-content: center; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h2 style="text-align: center; margin-bottom: 5px;">🚚 Supply Chain Comparison</h2>
        
        <!-- MASTER UI CONTROLS -->
        <div class="master-ui">
            <label>From:</label>
            <select id="master_from">
                {options_html}
            </select>
            
            <label>To:</label>
            <select id="master_to">
                {options_html}
            </select>
            
            <button onclick="triggerAnalysis()">Analyze Connection</button>
            <button class="reset" onclick="triggerReset()">Reset Maps</button>
        </div>

        <div class="controls">
            <label style="font-size: 14px; font-weight: 500;">View Mode:</label>
            <select id="viewMode" onchange="updateView()">
                <option value="split">Split Screen Comparison</option>
                <option value="exact">Exact Solver (Person 1)</option>
                <option value="meta">Metaheuristic (Person 2)</option>
            </select>
        </div>
    </div>
    
    <div class="content" id="content">
        <div class="frame-container" id="exact-container">
            <div class="frame-title" style="color: #0056b3;">Person 1: Exact Solver</div>
            <iframe id="frame-exact" src="Person_1/optimization_map.html?hide_ui=1"></iframe>
        </div>
        <div class="frame-container" id="meta-container">
            <div class="frame-title" style="color: #b33900;">Person 2: Metaheuristic (GA)</div>
            <iframe id="frame-meta" src="Person_2/metaheuristic_map.html?hide_ui=1"></iframe>
        </div>
    </div>

    <script>
        function triggerAnalysis() {{
            var fromPt = document.getElementById('master_from').value;
            var toPt = document.getElementById('master_to').value;
            if (!fromPt || !toPt) {{
                alert("Please select both a start and end point.");
                return;
            }}
            var exactFrame = document.getElementById('frame-exact');
            var metaFrame = document.getElementById('frame-meta');
            
            var params = "?hide_ui=1&from=" + encodeURIComponent(fromPt) + "&to=" + encodeURIComponent(toPt);
            exactFrame.src = "Person_1/optimization_map.html" + params;
            metaFrame.src = "Person_2/metaheuristic_map.html" + params;
        }}
        
        function triggerReset() {{
            document.getElementById('master_from').value = '';
            document.getElementById('master_to').value = '';
            document.getElementById('frame-exact').src = "Person_1/optimization_map.html?hide_ui=1";
            document.getElementById('frame-meta').src = "Person_2/metaheuristic_map.html?hide_ui=1";
        }}

        function updateView() {{
            var mode = document.getElementById('viewMode').value;
            var exactContainer = document.getElementById('exact-container');
            var metaContainer = document.getElementById('meta-container');
            
            if (mode === 'split') {{
                exactContainer.style.display = 'flex';
                metaContainer.style.display = 'flex';
            }} else if (mode === 'exact') {{
                exactContainer.style.display = 'flex';
                metaContainer.style.display = 'none';
            }} else if (mode === 'meta') {{
                exactContainer.style.display = 'none';
                metaContainer.style.display = 'flex';
            }}
        }}
    </script>
</body>
</html>
"""

with open("dashboard.html", "w") as f:
    f.write(html_content)
print("Dashboard rebuilt with master UI!")
