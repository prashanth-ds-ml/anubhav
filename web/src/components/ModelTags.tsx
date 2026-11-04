// Which model a measured result came from (owner, Nov 4): the agent that answered, and the model that mined lessons or
// proposed changes. Read from the experiments registry, so every page says the same.
const NAME = { open: "Muse Spark Open", spark: "Muse Spark 1.3", both: "Muse Spark Open and 1.3, compared" } as const;

export function ModelTags({ m }: { m?: { agent?: keyof typeof NAME; learning?: "spark" | "open" } }) {
  if (!m || (!m.agent && !m.learning)) return null;
  return (
    <span className="model-tags">
      {m.agent && <span className={`pill model-${m.agent}`} title="The model that answered or acted">{NAME[m.agent]}</span>}
      {m.learning && <span className={`pill model-${m.learning}`} title="The model that mined lessons or proposed changes">mining: {NAME[m.learning]}</span>}
    </span>
  );
}
