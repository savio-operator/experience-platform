import { Pool } from "pg";
import { TOTAL_CAP_MICRO_USD, RESERVATION_MICRO_USD } from "./chat-policy";

let pool: Pool | undefined;
function database() {
  if (!process.env.CHAT_DATABASE_URL) throw new Error("Usage store is not configured");
  pool ??= new Pool({ connectionString: process.env.CHAT_DATABASE_URL, max: 2, idleTimeoutMillis: 10000, connectionTimeoutMillis: 4000, statement_timeout: 5000 });
  return pool;
}
export async function quotaReady(): Promise<boolean> {
  try {
    const result = await database().query("SELECT reserved_micro_usd FROM demo_ai_budget WHERE id = 'elsewhere-demo' AND cap_micro_usd = $1", [TOTAL_CAP_MICRO_USD]);
    return result.rowCount === 1 && Number(result.rows[0].reserved_micro_usd) + RESERVATION_MICRO_USD <= TOTAL_CAP_MICRO_USD;
  } catch { return false; }
}
export async function reserveRequest(sessionHash: string): Promise<"ok" | "limit" | "rate"> {
  const client = await database().connect();
  try {
    await client.query("BEGIN");
    // Every server instance locks the same lifetime budget row before admission.
    const result = await client.query("SELECT reserved_micro_usd, cap_micro_usd FROM demo_ai_budget WHERE id = 'elsewhere-demo' FOR UPDATE");
    if (result.rowCount !== 1 || Number(result.rows[0].cap_micro_usd) !== TOTAL_CAP_MICRO_USD) throw new Error("Missing or invalid budget policy");
    if (Number(result.rows[0].reserved_micro_usd) + RESERVATION_MICRO_USD > TOTAL_CAP_MICRO_USD) { await client.query("ROLLBACK"); return "limit"; }
    const rate = await client.query(`SELECT
      count(*) FILTER (WHERE created_at > now() - interval '1 minute')::int AS minute,
      count(*) FILTER (WHERE session_hash = $1)::int AS session_day
      FROM demo_ai_attempts WHERE created_at > now() - interval '1 day'`, [sessionHash]);
    if (rate.rows[0].minute >= 20 || rate.rows[0].session_day >= 60) { await client.query("ROLLBACK"); return "rate"; }
    await client.query("UPDATE demo_ai_budget SET reserved_micro_usd = reserved_micro_usd + $1 WHERE id = 'elsewhere-demo'", [RESERVATION_MICRO_USD]);
    await client.query("INSERT INTO demo_ai_attempts (session_hash) VALUES ($1)", [sessionHash]);
    await client.query("COMMIT");
    return "ok";
  } catch (error) { await client.query("ROLLBACK").catch(() => {}); throw error; }
  finally { client.release(); }
}
