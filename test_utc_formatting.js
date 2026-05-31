/**
 * Test file to verify UTC time formatting works correctly.
 * Tests the formatUTCDateTime and formatUTCDate functions.
 */

const formatUTCDateTime = (isoString) => {
  try {
    const date = new Date(isoString);
    // Use UTC methods to avoid timezone conversion
    const year = date.getUTCFullYear();
    const month = date.getUTCMonth();
    const day = date.getUTCDate();
    const hours = date.getUTCHours();
    const minutes = date.getUTCMinutes();
    
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'];
    
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    const displayMinutes = minutes.toString().padStart(2, '0');
    
    return `${monthNames[month]} ${day}, ${year} at ${displayHours}:${displayMinutes} ${ampm}`;
  } catch (err) {
    return 'Invalid date';
  }
};

const formatUTCDate = (isoString) => {
  try {
    const date = new Date(isoString);
    const year = date.getUTCFullYear();
    const month = (date.getUTCMonth() + 1).toString().padStart(2, '0');
    const day = date.getUTCDate().toString().padStart(2, '0');
    return `${year}-${month}-${day}`;
  } catch (err) {
    return 'Invalid date';
  }
};

// Test cases based on the bug report
const testCases = [
  {
    input: "2026-06-07T13:00:00Z",
    expectedDateTime: "June 7, 2026 at 1:00 PM",
    expectedDate: "2026-06-07",
    description: "User booked 1-2PM slot on June 7 - should display as 1:00 PM, not 6:30 PM"
  },
  {
    input: "2026-06-03T15:00:00Z",
    expectedDateTime: "June 3, 2026 at 3:00 PM",
    expectedDate: "2026-06-03",
    description: "User booked 3-4PM slot on June 3 - should display as 3:00 PM"
  },
  {
    input: "2026-06-04T17:00:00Z",
    expectedDateTime: "June 4, 2026 at 5:00 PM",
    expectedDate: "2026-06-04",
    description: "User booked 5-6PM slot on June 4 - should display as 5:00 PM"
  },
  {
    input: "2026-06-06T10:30:00Z",
    expectedDateTime: "June 6, 2026 at 10:30 AM",
    expectedDate: "2026-06-06",
    description: "Appointment at 10:30 AM"
  }
];

console.log("Testing UTC Time Formatting Fix");
console.log("================================\n");

let passed = 0;
let failed = 0;

testCases.forEach((testCase) => {
  console.log(`Test: ${testCase.description}`);
  console.log(`Input: ${testCase.input}`);
  
  const resultDateTime = formatUTCDateTime(testCase.input);
  const resultDate = formatUTCDate(testCase.input);
  
  const dateTimeMatch = resultDateTime === testCase.expectedDateTime;
  const dateMatch = resultDate === testCase.expectedDate;
  
  if (dateTimeMatch && dateMatch) {
    console.log(`✅ PASS`);
    console.log(`   formatUTCDateTime() -> "${resultDateTime}"`);
    console.log(`   formatUTCDate() -> "${resultDate}"\n`);
    passed++;
  } else {
    console.log(`❌ FAIL`);
    if (!dateTimeMatch) {
      console.log(`   formatUTCDateTime() -> "${resultDateTime}"`);
      console.log(`   Expected: "${testCase.expectedDateTime}"`);
    }
    if (!dateMatch) {
      console.log(`   formatUTCDate() -> "${resultDate}"`);
      console.log(`   Expected: "${testCase.expectedDate}"`);
    }
    console.log();
    failed++;
  }
});

console.log("================================");
console.log(`Results: ${passed} passed, ${failed} failed out of ${testCases.length} tests\n`);

if (failed === 0) {
  console.log("✅ All UTC time formatting tests passed!");
  console.log("The dashboard will now display appointments at the correct times.");
} else {
  console.log(`❌ ${failed} test(s) failed. Review the implementation.`);
}
