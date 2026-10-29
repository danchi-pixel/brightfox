// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import type { Exam, LearnerHome as Home, LearnerTopicCard, MockCard } from "../learning/api";
import { englishExam, englishMock, subjectHomePath } from "../learning/english";
import EnglishPage from "./EnglishPage";
import LearnerHome from "./LearnerHome";

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ language: "sl", isAdmin: false }) }));
const topic: LearnerTopicCard = { id: "people", version: 5, subject: "english", title: "People are People", grade: 6, intro: "People notes", tasks: 25, learn: 6, levels: [1,2,3], extras: 0, challenge: 11, cards: 38, goals: 3, skills: 7, for: ["Erik"], has_parent_card: true, video: 0, oral: 5, runs: 4, finished: 2, last: null, challenge_state: {tasks: 11,unlocked:true,cleared:true}, study_state:{cards:38,known:["aunt","uncle"],goals:3,goal_ids:["a","b","c"],ticked:["a"]} };
const mock: MockCard & {last: {points:number;max:number} | null} = {id:"people-mock",subject:"english",title:"Poskusni test: People are People",version:2,grade:6,intro:"",minutes:30,topics:["people"],tasks:17,points:28,for:["Erik"],last:{points:21,max:28}};
const exam: Exam = {id:9,subject:"english",title:"English oral exam",exam_date:"2026-11-10",kind:"oral",target_grade:null,notes:"",result_grade:null,days_left:12,scope:[{topic_id:"people",skill_id:null,topic_title:topic.title}],readiness:0.7,skills:[]};
let client: QueryClient;
let home: Home;
let mocks: typeof mock[];
let failMocks: boolean;

beforeEach(() => {
  vi.stubGlobal("fetch",vi.fn(() => { throw new Error("No real server or AI in tests"); }));
  window.scrollTo = vi.fn();
  home={learner:{id:1,name:"Erik",grade:6,avatar:"",color:""},owner:true,lang:"sl",tutor:{configured:true,enabled:true,daily_limit:20,left_today:20},chats:[],topics:[topic,{...topic,id:"days",title:"Days, Dates & Hello"},{...topic,id:"science",title:"Erikovo naravoslovje",subject:"science",has_lab:true}]};
  mocks=[mock]; failMocks=false;
  vi.spyOn(api,"get").mockImplementation(async path => {
    if(path.includes("/home?")) return home;
    if(path.endsWith("/mocks")) { if(failMocks) throw new Error("Scratch network error"); return mocks; }
    if(path.includes("/exams/9?")) return {...exam,plan:{days:[],too_little_time:false,remaining:0}};
    if(path.includes("/exams?")) return [exam];
    if(path.includes("/mastery?")) return {topics:[{topic_id:"people",readiness:0.7}]};
    if(path.includes("/review?")) return {items:[],open:0,cleared:0};
    if(path.includes("/week?")) return {days:[],trophies:{cups:1,corrected:0}};
    throw new Error(`Unexpected GET: ${path}`);
  });
  vi.spyOn(api,"put").mockRejectedValue(new Error("Grouping must not write progress"));
  vi.spyOn(api,"post").mockRejectedValue(new Error("Grouping must not create content"));
  client=new QueryClient({defaultOptions:{queries:{retry:false,staleTime:Infinity}}});
});
afterEach(()=>{cleanup();client.clear();vi.restoreAllMocks();vi.unstubAllGlobals();});
function Location(){const l=useLocation();return <output data-testid="location">{l.pathname}{l.search}</output>;}
function mount(path:string){return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Location /><Routes><Route path="/l/:lid" element={<LearnerHome />} /><Route path="/l/:lid/english" element={<EnglishPage />} /><Route path="/l/:lid/practice/:tid" element={<p>Original practice screen</p>} /><Route path="/l/:lid/video/:tid" element={<p>Original video screen</p>} /><Route path="/l/:lid/mock/:mid" element={<p>Original mock screen</p>} /></Routes></MemoryRouter></QueryClientProvider>);}

describe("English collection",()=>{
  it("groups English only, keeping science and all originals intact",async()=>{
    const before=JSON.stringify(home);mount('/l/1');
    const entry=await screen.findByRole('link',{name:/Angleščina/});
    expect(entry.getAttribute('href')).toBe('/l/1/english');
    expect(screen.queryByText('People are People')).toBeNull();
    expect(screen.queryByText('Days, Dates & Hello')).toBeNull();
    expect(screen.queryByText(mock.title)).toBeNull();
    expect(screen.queryByText(exam.title)).toBeNull();
    expect(screen.getByRole('link',{name:/Erikovo naravoslovje/}).getAttribute('href')).toContain('/science/science');
    fireEvent.click(entry);
    await screen.findByRole('heading',{name:'Angleščina'});
    await screen.findByText(mock.title);
    expect(screen.getByText(exam.title)).toBeTruthy();
    expect(screen.getByRole('heading',{name:'People are People'})).toBeTruthy();
    expect(screen.getByRole('heading',{name:'Days, Dates & Hello'})).toBeTruthy();
    expect(JSON.stringify(home)).toBe(before);
    expect(api.put).not.toHaveBeenCalled();expect(api.post).not.toHaveBeenCalled();
  });
  it("retains the existing practice ID and every learning path",async()=>{
    mount('/l/1/english?view=study&topic=people');
    await screen.findAllByText('People are People');
    const buttons=screen.getAllByRole('button').map(b=>b.textContent);
    expect(buttons.some(t=>t?.includes('Uči se'))).toBe(true);
    expect(buttons.some(t=>t?.includes('Liga prvakov'))).toBe(true);
    expect(buttons.some(t=>t?.includes('Ustno'))).toBe(true);
    fireEvent.click(screen.getByRole('button',{name:/Vaja/}));
    expect(screen.getByTestId('location').textContent).toBe('/l/1/practice/people');
  });
  it("includes upstream video lessons inside the collection",async()=>{
    home.topics[0]={...topic,video:12};
    mount('/l/1/english?view=study&topic=people');
    fireEvent.click(await screen.findByRole('button',{name:/Video/}));
    expect(screen.getByTestId('location').textContent).toBe('/l/1/video/people');
  });
  it("shows saved progress and keeps the original mock route",async()=>{
    mount('/l/1/english?view=progress');
    await screen.findAllByText('Kartice: 2/38');
    expect(screen.getAllByText('Zaključene vaje: 2 · Vsi poskusi: 4')).toHaveLength(2);
    await screen.findByText(mock.title);
    fireEvent.click(screen.getByRole('button',{name:new RegExp(mock.title)}));
    expect(screen.getByTestId('location').textContent).toBe('/l/1/mock/people-mock');
  });
  it("includes standalone future English tests even without an English lesson",async()=>{
    home.topics=[];mocks=[{...mock,id:'future',title:'Future test',topics:[]}];mount('/l/1');
    fireEvent.click(await screen.findByRole('link',{name:/Angleščina/}));
    expect(await screen.findByText('Future test')).toBeTruthy();
  });
  it("reports unavailable test lists instead of claiming none exist",async()=>{
    failMocks=true;mount('/l/1/english?view=tests');
    await waitFor(()=>expect(screen.getByText(/Scratch network error/)).toBeTruthy());
    expect(screen.queryByText(/Trenutno ni testov/)).toBeNull();
  });
  it("groups by subject or related topic, and preserves other return paths",()=>{
    const ids=new Set(['people']);
    expect(englishMock({...mock,subject:'other'},ids)).toBe(true);
    expect(englishExam({...exam,subject:'other'},ids)).toBe(true);
    expect(englishMock({...mock,subject:'math',topics:['fractions']},ids)).toBe(false);
    expect(subjectHomePath(4,'english')).toBe('/l/4/english');
    expect(subjectHomePath(4,'math')).toBe('/l/4');
  });
});
