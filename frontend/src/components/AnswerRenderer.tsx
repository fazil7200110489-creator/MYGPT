import { RoleMatchCard } from './RoleMatchCard'
import { SkillsCard } from './SkillsCard'
import { ExperienceTimeline } from './ExperienceTimeline'
import { EducationCard } from './EducationCard'
import { ProjectsCard } from './ProjectsCard'
import { ContactCard } from './ContactCard'
import { SummaryCard } from './SummaryCard'
import { FileText, Building2, CheckCircle2 } from 'lucide-react'

export interface AnswerRendererProps {
  content: string
  question: string
  metadata?: any
}

export function AnswerRenderer({ content, question, metadata }: AnswerRendererProps) {
  const q = question.toLowerCase().trim()
  const c = content.trim()
  const lowerContent = c.toLowerCase()

  // 1. Role Suitability / Role Match Card
  const isRoleMatchQuery = q.includes('suitable') || q.includes('fit') || q.includes('role') || q.includes('work as') || lowerContent.includes('overall match') || lowerContent.includes('candidate belongs to')
  const hasAnswerYesNo = lowerContent.startsWith('answer:\nyes') || lowerContent.startsWith('answer:\nno') || lowerContent.startsWith('answer:\n') || lowerContent.startsWith('yes') || lowerContent.startsWith('no')

  if (isRoleMatchQuery && hasAnswerYesNo) {
    const isYes = lowerContent.includes('answer:\nyes') || lowerContent.startsWith('yes')
    const matchMatch = c.match(/(\d+)%/)
    const matchVal = matchMatch ? parseInt(matchMatch[1]) : (isYes ? 85 : 12)

    let tier = 'Not Suitable'
    if (matchVal >= 85) tier = 'Highly Suitable'
    else if (matchVal >= 60) tier = 'Suitable'
    else if (matchVal >= 35) tier = 'Partially Suitable'

    let reasonText = ''
    const reasonMatch = c.match(/Reason:\s*([\s\S]*?)(?=Evidence:|$)/i)
    if (reasonMatch) {
      reasonText = reasonMatch[1].trim()
    } else {
      reasonText = c.replace(/^(Answer:\s*(Yes|No)|Yes|No)[,\s\.]*/i, '').trim()
    }

    let evidenceText = 'Designation, Domain, Skills'
    const evidenceMatch = c.match(/Evidence:\s*([\s\S]*?)(?=Confidence:|$)/i)
    if (evidenceMatch) {
      evidenceText = evidenceMatch[1].trim()
    }

    const matchingSkills = (c.match(/matching skills:\s*([^\n]+)/i)?.[1] || '').split(',').map(s => s.trim()).filter(Boolean)
    const missingSkills = (c.match(/missing skills:\s*([^\n]+)/i)?.[1] || '').split(',').map(s => s.trim()).filter(Boolean)

    return (
      <RoleMatchCard
        matchPercentage={matchVal}
        suitabilityTier={tier}
        isQualified={isYes}
        matchingSkills={matchingSkills}
        missingSkills={missingSkills}
        reason={reasonText}
        evidence={evidenceText}
        confidence={metadata?.confidence || 95}
      />
    )
  }

  // 2. Candidate Information / Contact Grid
  if (lowerContent.includes('candidate information') || lowerContent.includes('contact details') || (c.includes('Email:') && c.includes('Phone:'))) {
    const lines = c.split('\n').map(l => l.trim()).filter(Boolean)
    const contactFields: Record<string, string> = {
      name: 'Not Available',
      email: 'Not Available',
      phone: 'Not Available',
      address: 'Not Available',
      linkedin: 'Not Available',
      github: 'Not Available',
      portfolio: 'Not Available'
    }

    lines.forEach(line => {
      const parts = line.split(':')
      if (parts.length >= 2) {
        const key = parts[0].replace(/^[•\-\*]/, '').trim().toLowerCase()
        const val = parts.slice(1).join(':').trim()
        if (key.includes('name')) contactFields.name = val || 'Not Available'
        else if (key.includes('email')) contactFields.email = val || 'Not Available'
        else if (key.includes('phone') || key.includes('mobile')) contactFields.phone = val || 'Not Available'
        else if (key.includes('address') || key.includes('location')) contactFields.address = val || 'Not Available'
        else if (key.includes('linkedin')) contactFields.linkedin = val || 'Not Available'
        else if (key.includes('github')) contactFields.github = val || 'Not Available'
        else if (key.includes('portfolio')) contactFields.portfolio = val || 'Not Available'
      }
    })

    return (
      <ContactCard
        name={contactFields.name}
        email={contactFields.email}
        phone={contactFields.phone}
        address={contactFields.address}
        linkedin={contactFields.linkedin}
        github={contactFields.github}
        portfolio={contactFields.portfolio}
      />
    )
  }

  // 3. Domain Intent Card
  if (q.includes('domain') || q.includes('industry') || q.includes('sector')) {
    return (
      <div className="flex items-center gap-4 p-4 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200 rounded-2xl shadow-sm my-1">
        <div className="h-11 w-11 bg-indigo-600 text-white rounded-xl flex items-center justify-center font-bold text-lg shadow-sm shrink-0">
          <Building2 className="h-6 w-6" />
        </div>
        <div>
          <div className="text-[10px] uppercase font-bold text-indigo-700 tracking-wider">Detected Industry Domain</div>
          <div className="text-slate-900 font-extrabold text-sm mt-0.5">{c}</div>
        </div>
      </div>
    )
  }

  // Helper function to parse multiline text
  const parseBlocks = (text: string) => {
    const lines = text.split('\n').map(l => l.trim()).filter(Boolean)
    if (lines.length === 0) return []
    const blocks: { title: string; details: string[] }[] = []
    let currentBlock: { title: string; details: string[] } | null = null

    for (const line of lines) {
      const isBullet = line.startsWith('•') || line.startsWith('-') || line.startsWith('*') || /^\d+[\.\)]/.test(line)
      const cleanedText = line.replace(/^[•\-\*\d\.\)\s]+/, '').replace(/\*\*/g, '').trim()
      
      if (!cleanedText) continue

      if (isBullet || !currentBlock) {
        currentBlock = { title: cleanedText, details: [] }
        blocks.push(currentBlock)
      } else {
        currentBlock.details.push(cleanedText)
      }
    }
    return blocks
  }

  // 4. Projects Card
  if (q.includes('project') || lowerContent.includes('project name')) {
    if (lowerContent.includes('no project information is available')) {
      return <ProjectsCard projects={[]} noProjectsAvailable={true} />
    }
    const blocks = parseBlocks(c)
    if (blocks.length > 0) {
      const projectItems = blocks.map(b => ({
        title: b.title,
        responsibilities: b.details
      }))
      return <ProjectsCard projects={projectItems} />
    }
  }

  // 5. Experience Timeline Card
  if (q.includes('experience') || q.includes('work') || q.includes('job') || q.includes('company') || q.includes('employment')) {
    const blocks = parseBlocks(c)
    if (blocks.length > 0) {
      const expItems = blocks.map(b => ({
        title: b.title,
        responsibilities: b.details
      }))
      const totalExpMatch = c.match(/Total Experience:\s*([^\n]+)/i)?.[1]
      return <ExperienceTimeline totalExperience={totalExpMatch} experiences={expItems} />
    }
  }

  // 6. Education Card
  if (q.includes('education') || q.includes('study') || q.includes('college') || q.includes('degree') || q.includes('university')) {
    const blocks = parseBlocks(c)
    if (blocks.length > 0) {
      const eduItems = blocks.map(b => ({
        degree: b.title,
        details: b.details
      }))
      return <EducationCard educations={eduItems} />
    }
  }

  // 7. Skills Card
  if (q.includes('skills') || q.includes('technical') || q.includes('expert') || q.includes('competenc')) {
    const blocks = parseBlocks(c)
    if (blocks.length > 0) {
      const skillList = blocks.map(b => b.title)
      return <SkillsCard allSkills={skillList} />
    }
  }

  // 8. Summary Card
  if (q.includes('summarize') || q.includes('summary') || q.includes('overview') || q.includes('brief')) {
    const candidateName = metadata?.entities?.name || 'Candidate'
    const designation = metadata?.entities?.designation || 'Professional Specialist'
    const domain = metadata?.entities?.domain || 'Enterprise Industry'
    const experience = metadata?.entities?.experience || 'Work Experience Available'
    const education = metadata?.entities?.education || 'Academic Credentials'

    return (
      <SummaryCard
        name={candidateName}
        designation={designation}
        domain={domain}
        experience={experience}
        education={education}
        summaryText={c}
      />
    )
  }

  // 9. Structured Markdown Prose Renderer (High Contrast Default)
  const lines = c.split('\n').map(l => l.trim()).filter(Boolean)

  return (
    <div className="flex flex-col gap-3 my-1">
      <div className="flex items-center gap-2 font-extrabold text-slate-900 text-xs uppercase tracking-wider border-b border-slate-200 pb-2">
        <FileText className="h-4 w-4 text-indigo-600" />
        <span>Executive Analysis</span>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm flex flex-col gap-2.5">
        {lines.map((line, idx) => {
          const isBullet = line.startsWith('•') || line.startsWith('-') || line.startsWith('*') || /^\d+[\.\)]/.test(line)
          const cleanLine = line.replace(/^[•\-\*\d\.\)\s]+/, '').replace(/\*\*/g, '').trim()

          if (isBullet) {
            return (
              <div key={idx} className="flex items-start gap-2 text-xs font-semibold text-slate-800 leading-relaxed">
                <CheckCircle2 className="h-3.5 w-3.5 text-indigo-600 shrink-0 mt-0.5" />
                <span>{cleanLine}</span>
              </div>
            )
          }

          return (
            <p key={idx} className="text-xs font-semibold text-slate-800 leading-relaxed">
              {line.replace(/\*\*/g, '')}
            </p>
          )
        })}
      </div>
    </div>
  )
}
