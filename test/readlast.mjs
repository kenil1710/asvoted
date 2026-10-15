import { connect, argOf } from "./harness.mjs";
import { writeFileSync } from "node:fs";
const { view } = connect({ address: argOf("address"), role: "probe" });
const last = await view("get_last");
if (argOf("out")) writeFileSync(argOf("out"), typeof last === "string" ? last : JSON.stringify(last));
console.log(String(last).slice(0, Number(argOf("n", "20000"))));
