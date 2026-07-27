import { RoleMatchCard } from './RoleMatchCard'
import { SkillsCard } from './SkillsCard'
import { ExperienceTimeline } from './ExperienceTimeline'
import { EducationCard } from './EducationCard'
import { ProjectsCard } from './ProjectsCard'
import { ContactCard } from './ContactCard'
import { SummaryCard } from './SummaryCard'
import { Building2 } from 'lucide-react'

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
  const isRoleMatchQuery = q.includes('role suitability') || q.includes('fit for role') || q.includes('suitable for role') || lowerContent.includes('overall match:')
  const hasAnswerYesNo = lowerContent.startsWith('answer:\nyes') || lowerContent.startsWith('answer:\nno')

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

  // 8. Multi-Candidate Summary Cards
  if (q.includes('summarize') || q.includes('summary') || q.includes('overview') || q.includes('brief') || lowerContent.includes('candidate profile summary')) {
    const candidateBlocks = c.split(/####\s*👤?\s*\*\*/).filter(b => b.trim().length > 0)

    if (candidateBlocks.length > 1) {
      return (
        <div className="flex flex-col gap-4 my-2">
          {candidateBlocks.map((block, idx) => {
            const blockContent = '#### **' + block
            const candidateName = block.split('**')[0]?.trim() || `Candidate ${idx+1}`
            const designation = blockContent.match(/Current Role:\s*\*?([^\*\n]+)\*?/i)?.[1] || 'Professional Specialist'
            const experience = blockContent.match(/Experience:\s*([^\n]+)/i)?.[1] || 'Experience Available'
            const education = blockContent.match(/Education:\s*([^\n]+)/i)?.[1] || 'Credentials Available'
            const skillsMatch = blockContent.match(/Technical Skills:\s*([^\n]+)/i)?.[1]
            const skillsList = skillsMatch ? skillsMatch.split(',').map(s => s.trim()) : []
            const projMatch = blockContent.match(/Projects:\s*([^\n]+)/i)?.[1]
            const projList = projMatch ? projMatch.split(',').map(p => p.trim()) : []
            const recMatch = blockContent.match(/Recommended Roles:\s*([^\n]+)/i)?.[1]
            const recList = recMatch ? recMatch.split(',').map(r => r.trim()) : []

            return (
              <SummaryCard
                key={idx}
                name={candidateName}
                currentRole={designation}
                designation={designation}
                domain="Enterprise Industry"
                experience={experience}
                education={education}
                skills={skillsList}
                projects={projList}
                recommendedRoles={recList}
                confidence={92 - (idx * 2)}
                summaryText={blockContent}
              />
            )
          })}
        </div>
      )
    }

    const candidateName = c.match(/####\s*👤?\s*\*\*([^\*]+)\*\*/)?.[1] || metadata?.entities?.name || 'Candidate'
    const designation = c.match(/Current Role:\s*\*?([^\*\n]+)\*?/i)?.[1] || metadata?.entities?.designation || 'Professional Specialist'
    const domain = metadata?.entities?.domain || 'Enterprise Industry'
    const experience = c.match(/Experience:\s*([^\n]+)/i)?.[1] || metadata?.entities?.experience || 'Work Experience Available'
    const education = c.match(/Education:\s*([^\n]+)/i)?.[1] || metadata?.entities?.education || 'Academic Credentials'
    const skillsMatch = c.match(/Technical Skills:\s*([^\n]+)/i)?.[1]
    const skillsList = skillsMatch ? skillsMatch.split(',').map(s => s.trim()) : (metadata?.entities?.skills || [])
    const projMatch = c.match(/Projects:\s*([^\n]+)/i)?.[1]
    const projList = projMatch ? projMatch.split(',').map(p => p.trim()) : (metadata?.entities?.projects || [])
    const recMatch = c.match(/Recommended Roles:\s*([^\n]+)/i)?.[1]
    const recList = recMatch ? recMatch.split(',').map(r => r.trim()) : (metadata?.insights?.recommended_roles || [])

    return (
      <SummaryCard
        name={candidateName}
        currentRole={designation}
        designation={designation}
        domain={domain}
        experience={experience}
        education={education}
        skills={skillsList}
        projects={projList}
        recommendedRoles={recList}
        confidence={metadata?.confidence || 92}
        summaryText={c}
      />
    )
  }

  // 9. Conversational Markdown & Table Renderer
  const rawLines = c.split('\n').map(l => l.trim()).filter(Boolean)
  const isTableLine = (line: string) => line.startsWith('|') && line.endsWith('|')

  // Check if content contains markdown table
  const hasTable = rawLines.some(isTableLine)

  if (hasTable) {
    const tableLines = rawLines.filter(isTableLine)
    const nonTableLines = rawLines.filter(l => !isTableLine(l))

    // Parse header and rows
    const rows = tableLines
      .filter(l => !l.includes(':---') && !l.includes('---'))
      .map(l => l.split('|').map(cell => cell.trim()).filter(Boolean))

    const headers = rows.length > 0 ? rows[0] : []
    const bodyRows = rows.slice(1)

    return (
      <div className="flex flex-col gap-3 my-2 text-xs">
        {/* Render Non-Table Text Header */}
        {nonTableLines.map((line, idx) => {
          if (line.startsWith('#')) {
            return (
              <h3 key={idx} className="font-extrabold text-slate-900 text-xs uppercase tracking-wider border-b border-slate-200 pb-1 flex items-center gap-1 text-purple-900">
                {line.replace(/^#+\s*/, '')}
              </h3>
            )
          }
          return <p key={idx} className="text-slate-800 font-medium">{line.replace(/\*\*/g, '')}</p>
        })}

        {/* Render Styled Table */}
        {headers.length > 0 && (
          <div className="overflow-x-auto border border-slate-200 rounded-xl shadow-2xs bg-white">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100/80 border-b border-slate-200 font-extrabold text-slate-900 text-[11px] uppercase tracking-wider">
                  {headers.map((h, i) => (
                    <th key={i} className="p-2.5">{h.replace(/\*\*/g, '')}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {bodyRows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-indigo-50/30 transition-colors">
                    {row.map((cell, cIdx) => {
                      const cleanCell = cell.replace(/\*\*/g, '')
                      const isRank = cleanCell.startsWith('#')
                      const isScore = cleanCell.includes('/100') || cleanCell.includes('%')

                      return (
                        <td key={cIdx} className="p-2.5">
                          {isRank ? (
                            <span className="bg-purple-100 text-purple-900 border border-purple-300 font-black px-2 py-0.5 rounded-md text-[11px]">
                              {cleanCell}
                            </span>
                          ) : isScore ? (
                            <span className="bg-emerald-100 text-emerald-900 font-black px-2 py-0.5 rounded-md text-[11px]">
                              {cleanCell}
                            </span>
                          ) : (
                            cleanCell
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 my-1 text-xs text-slate-800 font-medium leading-relaxed">
      {rawLines.map((line, idx) => {
        if (line.startsWith('### ') || line.startsWith('#### ') || line.startsWith('## ')) {
          const headingText = line.replace(/^#+\s*/, '')
          return (
            <h3 key={idx} className="font-extrabold text-slate-900 text-xs uppercase tracking-wider border-b border-slate-200 pb-1 mt-1 mb-0.5 flex items-center gap-1.5 text-purple-900">
              {headingText}
            </h3>
          )
        }

        const isBullet = line.startsWith('•') || line.startsWith('-') || line.startsWith('*') || /^\d+[\.\)]/.test(line)
        const cleanLine = line.replace(/^[•\-\*\d\.\)\s]+/, '').replace(/\*\*/g, '').trim()

        if (isBullet) {
          return (
            <div key={idx} className="flex items-start gap-2 text-xs font-medium text-slate-800 leading-relaxed pl-1">
              <span className="text-purple-600 font-bold">•</span>
              <span>{cleanLine}</span>
            </div>
          )
        }

        return (
          <p key={idx} className="text-xs font-medium text-slate-800 leading-relaxed">
            {line.replace(/\*\*/g, '')}
          </p>
        )
      })}
    </div>
  )
}
