import re

with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

# 1. Fix the colormap to match PIDtoolbox exactly ("hot")
target_cmap = r'''def _make_thermal_colormap\(\):
    positions = \[0\.0, 0\.2, 0\.4, 0\.6, 0\.8, 1\.0\]
    colors = \[
        \(0, 0, 0\),        # Black
        \(0, 0, 128\),      # Dark Blue
        \(0, 255, 255\),    # Cyan
        \(0, 255, 0\),      # Green
        \(255, 255, 0\),    # Yellow
        \(255, 0, 0\)       # Red
    \]
    return pg\.ColorMap\(positions, colors\)'''

replacement_cmap = """def _make_thermal_colormap():
    positions = [0.0, 0.25, 0.5, 0.75, 1.0]
    colors = [
        (0, 0, 0),        # Black
        (128, 0, 0),      # Dark Red
        (255, 100, 0),    # Orange
        (255, 255, 0),    # Yellow
        (255, 255, 255)   # White
    ]
    return pg.ColorMap(positions, colors)"""

code = re.sub(target_cmap, replacement_cmap, code)


# 2. Modify _render_heatmap to add the labels inside the plot like PIDtoolbox
target_render = r'''            tr = pg\.QtGui\.QTransform\(\)
            tr\.scale\(100\.0 / img\.shape\[0\], freq_max / img\.shape\[1\]\)
            
            view\.setImage\(img, autoRange=False, autoLevels=True, transform=tr\)
            
            view\.getView\(\)\.setLimits\(xMin=0, xMax=100, yMin=0, yMax=freq_max\)'''

replacement_render = """            tr = pg.QtGui.QTransform()
            tr.scale(100.0 / img.shape[0], freq_max / img.shape[1])
            
            # Use specific levels based on data percentiles to mimic PIDtoolbox contrast
            v_min, v_max = np.nanmin(img), np.nanpercentile(img, 99.5)
            if np.isnan(v_max) or v_min == v_max: v_max = v_min + 1
            
            view.setImage(img, autoRange=False, levels=(v_min, v_max), transform=tr)
            
            # Add PIDtoolbox style labels inside the plot
            mean_val = np.nanmean(img)
            peak_val = np.nanmax(img)
            
            axis_label = pg.TextItem(axis, color=(255, 255, 255), anchor=(0, 0))
            axis_label.setPos(2, freq_max - (freq_max * 0.05))
            view.getView().addItem(axis_label)
            
            stats_label = pg.TextItem(f"mean={mean_val:.3f}\\npeak={peak_val:.3f}", color=(255, 255, 255), anchor=(1, 0))
            stats_label.setPos(98, freq_max - (freq_max * 0.05))
            view.getView().addItem(stats_label)
            
            view.getView().setLimits(xMin=0, xMax=100, yMin=0, yMax=freq_max)"""

code = re.sub(target_render, replacement_render, code)

# Fix plot title to be empty since we put the axis name inside the plot
target_title = r'plot_item = pg\.PlotItem\(title=axis\.capitalize\(\)\)'
replacement_title = 'plot_item = pg.PlotItem(title="")'
code = re.sub(target_title, replacement_title, code)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
