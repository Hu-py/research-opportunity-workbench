import { redirect } from "next/navigation";

/** V0.5: reproduce the approved standalone HTML without legacy Workbench modules. */
export default function Home() {
  redirect("/research-atlas-v0.5.html");
}
