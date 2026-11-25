import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { alpha, useTheme } from "@mui/material/styles";

/** Horizontal stacked bars: points earned vs. points still available for each scoring rule. */
export default function ScoreBreakdownChart({ breakdown = [], height = 280 }) {
  const theme = useTheme();
  const data = breakdown.map((b) => ({
    name: b.label,
    "Points earned": b.points,
    "Points available": Math.max(b.max - b.points, 0),
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
        <CartesianGrid horizontal={false} stroke={theme.palette.divider} />
        <XAxis type="number" tick={{ fill: theme.palette.text.secondary, fontSize: 12 }} axisLine={false} tickLine={false} />
        <YAxis
          type="category"
          dataKey="name"
          width={150}
          tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: alpha(theme.palette.text.primary, 0.05) }}
          contentStyle={{
            background: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 8,
            color: theme.palette.text.primary,
          }}
        />
        <Bar dataKey="Points earned" stackId="score" fill={theme.palette.primary.main} radius={[4, 0, 0, 4]} />
        <Bar dataKey="Points available" stackId="score" fill={alpha(theme.palette.text.primary, 0.14)} radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
