// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import SciencePage from "./SciencePage";
import type { Availability, Bank, Progress, Question } from "./types";

vi.mock("@/lib/auth", () => ({useAuth:()=>({language:"sl"})}));
const q: Question={id:"note",topic:"shared",kind:"oral",prompt:"Notebook question",answer:"Notebook answer",points:["Point"],hints:["Hint"],sources:["n"],difficulty:1,card:true};
const bank: Bank={title:"Naravoslovje",lessons:[{id:"shared",title:"Shared topic",icon:"",summary:"Summary",notes:["Combined notes"],vocabulary:{},sources:["n","t"]}],questions:[q,{...q,id:"book",prompt:"Textbook question",answer:"Textbook answer",sources:["t"]},{...q,id:"mixed",prompt:"Mixed question",sources:["n","t"]}],sources:[{id:"n",file:"n.jpg",group:"notebook",label:"Notebook source",width:100,height:100,rotate:0,review:""},{id:"t",file:"t.jpg",group:"textbook",label:"Textbook source",width:100,height:100,rotate:0,review:""}],review_notes:[]};
const saved: Progress={revision:8,session:{mode:"oral",queue:["book"],index:0,ratings:{}},answers:{"practice:book":{rating:"know",attempts:4,due:"2030-01-01",interval:4,updated:""}}};
let scope: Availability;
let client: QueryClient;
beforeEach(()=>{
  scope={enabled_lessons:[],active_questions:["note"],question_groups:{note:"notebook",book:"textbook",mixed:"review"},can_manage:false};
  vi.stubGlobal("fetch",vi.fn(()=>{throw new Error("No real data or AI in tests");}));
  window.scrollTo=vi.fn();
  vi.spyOn(api,"get").mockImplementation(async path=>{
    if(path.includes("/home?")) return {owner:!scope.can_manage,learner:{name:"Erik"},topics:[]};
    if(path.endsWith("/progress")) return saved;
    if(path.endsWith("/availability")) return scope;
    if(path.endsWith("/topics/science")) return {id:"science",version:5,lab:bank};
    throw new Error(`Unexpected ${path}`);
  });
  vi.spyOn(api,"put").mockImplementation(async(path, payload)=>{
    if(!path.endsWith("/availability/shared")) throw new Error("Browsing must not write progress");
    const enabled=(payload as {enabled:boolean}).enabled;
    scope={...scope,enabled_lessons:enabled?["shared"]:[],active_questions:enabled?["note","book"]:["note"]};
    return scope;
  });
  client=new QueryClient({defaultOptions:{queries:{retry:false}}});
});
afterEach(()=>{cleanup();client.clear();vi.restoreAllMocks();vi.unstubAllGlobals();});
function mount(){render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/l/1/science/science"]}><Routes><Route path="/l/:lid/science/:tid" element={<SciencePage/>}/></Routes></MemoryRouter></QueryClientProvider>);}
const click=(name:RegExp|string)=>fireEvent.click(screen.getByRole("button",{name}));
describe("Source groups",()=>{
  it("defaults to notebook, keeps textbook viewable but inactive and excludes old progress",async()=>{
    mount();await screen.findByRole("heading",{name:"Zvezek"});
    expect((screen.getByRole("button",{name:"Vadim ustno"}) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.queryByRole("button",{name:/Nadaljuj učenje/})).toBeNull();
    click(/^📚 Učbenik/);
    expect((screen.getByRole("button",{name:"Vadim ustno"}) as HTMLButtonElement).disabled).toBe(true);
    click("Moj napredek");expect(screen.queryByRole("heading",{name:"Shared topic"})).toBeNull();
    click("Učenje po temah");fireEvent.click(screen.getByText("Textbook question"));
    expect(screen.getByText("Textbook answer")).toBeTruthy();
    expect(screen.queryByRole("button",{name:"Aktiviraj temo"})).toBeNull();
    expect(api.put).not.toHaveBeenCalled();
  });
  it("lets a parent activate one topic and restores its prior progress without rewriting it",async()=>{
    scope.can_manage=true;mount();await screen.findByRole("heading",{name:"Zvezek"});
    click(/^📚 Učbenik/);click("Učenje po temah");click("Aktiviraj temo");
    await screen.findByRole("button",{name:"Prestavi za kasneje"});
    expect(api.put).toHaveBeenCalledWith("/api/learners/1/topics/science/lab/availability/shared",{version:5,enabled:true});
    click("Moj napredek");expect(screen.getByText("1/1 vprašanj v vaji · 1 znam")).toBeTruthy();
    click("Učenje po temah");click("Prestavi za kasneje");await screen.findByRole("button",{name:"Aktiviraj temo"});
    click("Moj napredek");await waitFor(()=>expect(screen.queryByText("1/1 vprašanj v vaji · 1 znam")).toBeNull());
    expect(saved.answers["practice:book"].attempts).toBe(4);
    expect(api.put).toHaveBeenCalledTimes(2);
  });
  it("flags mixed provenance without offering practice or activation",async()=>{
    scope.can_manage=true;mount();await screen.findByRole("heading",{name:"Zvezek"});
    click(/^⚑ Za pregled/);click("Učenje po temah");
    expect(screen.getByText("Mixed question")).toBeTruthy();
    expect((screen.getByRole("button",{name:"Razložim na glas"}) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole("button",{name:"Aktiviraj temo"})).toBeNull();
  });
});
