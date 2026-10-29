"""Minimal Flet chart test — does BarChart render at all in this environment?"""
import flet as ft
from flet_charts import BarChart, BarChartGroup, BarChartRod, ChartAxis, ChartAxisLabel


def main(page: ft.Page):
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0F1115"

    groups = []
    for i in range(7):
        groups.append(BarChartGroup(
            x=i,
            rods=[BarChartRod(from_y=0, to_y=20 + i * 10, width=22,
                              color="#7E8CE0", border_radius=4)],
        ))

    chart = BarChart(
        groups=groups,
        animation=ft.Animation(300, ft.AnimationCurve.EASE),
        bgcolor="#1A1D24",
        left_axis=ChartAxis(label_size=30, show_labels=True, labels=[
            ChartAxisLabel(value=0, label=ft.Text("0", size=10)),
            ChartAxisLabel(value=50, label=ft.Text("50", size=10)),
            ChartAxisLabel(value=100, label=ft.Text("100", size=10)),
        ]),
        bottom_axis=ChartAxis(label_size=28, show_labels=True, labels=[
            ChartAxisLabel(value=i, label=ft.Text(str(i), size=10))
            for i in range(7)
        ]),
        horizontal_grid_lines=30,
        min_y=0,
        max_y=120,
        group_spacing=18,
    )

    # Wrap in a Container with explicit height
    page.add(
        ft.Column(
            [
                ft.Text("Bar chart test", size=18, color="#FFFFFF"),
                ft.Container(
                    content=chart,
                    height=200,
                    bgcolor="#22262F",
                    border_radius=8,
                ),
            ],
            spacing=10,
        )
    )


if __name__ == "__main__":
    ft.run(main)
