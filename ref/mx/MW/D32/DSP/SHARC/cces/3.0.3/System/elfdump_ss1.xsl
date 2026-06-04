<?xml version="1.0"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/TR/WD-xsl">

  <xsl:template match ="/">
    <HTML xmlns:xsl="http://www.w3.org/TR/WD-xsl">

    <BODY>
      <xsl:apply-templates select="DOCUMENT"/>
    </BODY>

    <SCRIPT>
    <![CDATA[
    function changeSectionRepresention(rep) {
      for (i = 0; i != 3; i++)  {
        window.event.srcElement.parentElement.children(6).children(i).style.display = 
            (i == rep) ? "" : "none";
        }
    }
    ]]>
    </SCRIPT>

    </HTML>
  </xsl:template>

  <xsl:template match="DOCUMENT">
    <xsl:apply-templates select="OBJECT_FILE"/>
    <xsl:apply-templates select="ARCHIVE_ELEMENT"/>
  </xsl:template> 

  <xsl:template match="OBJECT_FILE">
    <xsl:apply-templates select="*"/>
  </xsl:template>

  <xsl:template match="ARCHIVE_ELEMENT">
    <H1>
      <U>Archive element <xsl:value-of select="@name"/></U>
    </H1>
    <xsl:apply-templates select="OBJECT_FILE"/>
    <P/><HR size="10" noshade="1"/>
  </xsl:template> 

  <xsl:template match="ELF_PROGRAM_HEADERS">
    <H1>
      Program Headers
    </H1>
    <TABLE border="1" width="100%" cellpadding="0" cellspacing="0">
    <THEAD bgcolor="#006fff">
      <TR>
        <TH>Type</TH>
        <TH>Offset</TH>
        <TH>Vaddr</TH>
        <TH>Paddr</TH>
        <TH>Filesz</TH>
        <TH>Memsz</TH>
        <TH>Flags</TH>
        <TH>Align</TH>
      </TR>
    </THEAD>
    <TBODY bgolor="#88ccff">
      <xsl:apply-templates select="PROGRAM_HEADER"/>
    </TBODY>
    </TABLE>
    <P/><HR size="6" noshade="1"/>
  </xsl:template> 

  <xsl:template match="PROGRAM_HEADER">
    <TR>
      <TD align="right"><xsl:value-of select="@type"/></TD>
      <TD align="right"><xsl:value-of select="@offset"/></TD>
      <TD align="right"><xsl:value-of select="@vaddr"/></TD>
      <TD align="right"><xsl:value-of select="@paddr"/></TD>
      <TD align="right"><xsl:value-of select="@filesz"/></TD>
      <TD align="right"><xsl:value-of select="@memsz"/></TD>
      <TD align="right"><xsl:value-of select="@flags"/></TD>
      <TD align="right"><xsl:value-of select="@align"/></TD>
    </TR>
  </xsl:template>

  <xsl:template match="ELF_SECTION_HEADERS">
    <H1>
      Sections
    </H1>
    <TABLE border="1" width="100%" cellpadding="0" cellspacing="0">
    <THEAD bgcolor="#006fff">
      <TR>
        <TH>Index</TH>
        <TH>Name</TH>
        <TH>Type</TH>
        <TH>Flags</TH>
        <TH>Address</TH>
        <TH>Offset</TH>
        <TH>Size (bytes)</TH>
        <TH>Link</TH>
        <TH>Info</TH>
        <TH>Align</TH>
        <TH>Entry size</TH>
      </TR>
    </THEAD>
    <TBODY bgolor="#88ccff">
      <xsl:apply-templates select="SECTION_HEADER"/>
    </TBODY>
    </TABLE>
    <P/><HR size="6" noshade="1"/>
  </xsl:template> 

  <xsl:template match="SECTION_HEADER">
    <TR>
      <TD><xsl:value-of select="@index"/></TD>
      <TD>
        <A>
            <xsl:attribute name="href">#SECTION_<xsl:value-of select="@index"/></xsl:attribute>
            <xsl:value-of select="@name"/>
        </A>
      </TD>
      <TD><xsl:value-of select="@type_name"/></TD>
      <TD align="right"><xsl:value-of select="@flags"/></TD>
      <TD align="right"><xsl:value-of select="@address"/></TD>
      <TD align="right"><xsl:value-of select="@offset"/></TD>
      <TD align="right"><xsl:value-of select="@size"/></TD>
      <TD align="right"><xsl:value-of select="@link"/></TD>
      <TD align="right"><xsl:value-of select="@info"/></TD>
      <TD align="right"><xsl:value-of select="@align"/></TD>
      <TD align="right"><xsl:value-of select="@entry_size"/></TD>
    </TR>
  </xsl:template>

  <xsl:template match="SECTION_PROGBITS[@type='Hex+Ascii+Instructions']">
    <H2>
      <A><xsl:attribute name="name">#SECTION_<xsl:value-of select="@index"/></xsl:attribute></A>
      Section <xsl:value-of select="@name"/>
    </H2>
    <xsl:if test="HEX_REPRESENTATION">
      <input type="radio" onclick="changeSectionRepresention(0)" checked="">
        <xsl:attribute name="name">section_button_<xsl:value-of select="@index"/></xsl:attribute>
        Hex
      </input>
    </xsl:if>
    <xsl:if test="HEX_ASCII_REPRESENTATION">
      <input type="radio" onclick="changeSectionRepresention(1)">
        <xsl:attribute name="name">section_button_<xsl:value-of select="@index"/></xsl:attribute>
        Hex + Ascii
      </input>
    </xsl:if>
    <xsl:if test="HEX_INSTR_REPRESENTATION">
      <input type="radio" onclick="changeSectionRepresention(2)">
        <xsl:attribute name="name">section_button_<xsl:value-of select="@index"/></xsl:attribute>
        Hex + Instructions
      </input>
    </xsl:if>
    <P/>

    <xsl:apply-templates select="HEX_REPRESENTATION|HEX_ASCII_REPRESENTATION|HEX_INSTR_REPRESENTATION"/>
    <P/><HR size="4" noshade="1"/>
  </xsl:template>

  <xsl:template match="HEX_REPRESENTATION">
    <TABLE width="100%" border="1" cellpadding="1" cellspacing="0">
    <TBODY bgolor="#88ccff">
      <xsl:for-each select="PROGBITS_ENTRY">
      <TR>
        <TD align="right"><xsl:value-of select="@offset"/></TD>
        <TD><PRE/><xsl:value-of select="HEX_STRING"/></TD>
      </TR>
      </xsl:for-each>
    </TBODY>
    </TABLE>
  </xsl:template>

  <xsl:template match="HEX_ASCII_REPRESENTATION">
    <TABLE style="display:none" width="100%" border="1" cellpadding="1" cellspacing="0">
    <TBODY bgolor="#88ccff">
      <xsl:for-each select="PROGBITS_ENTRY">
      <TR>
        <TD align="right"><xsl:value-of select="@offset"/></TD>
        <TD><PRE/><xsl:value-of select="HEX_STRING"/></TD>
        <TD><PRE/><xsl:value-of select="ASCII_STRING"/></TD>
      </TR>
      </xsl:for-each>
    </TBODY>
    </TABLE>
  </xsl:template>

  <xsl:template match="HEX_INSTR_REPRESENTATION">
    <TABLE style="display:none" width="100%" border="1" cellpadding="1" cellspacing="0">
    <TBODY bgolor="#88ccff">
      <xsl:for-each select="PROGBITS_ENTRY">
      <TR>
        <TD align="right"><xsl:value-of select="@address"/></TD>
        <TD><PRE/><xsl:value-of select="HEX_STRING"/></TD>
        <TD><PRE/><xsl:value-of select="INSTRUCTION"/></TD>
      </TR>
      </xsl:for-each>
    </TBODY>
    </TABLE>
  </xsl:template>

  <xsl:template match="SECTION_PROCESSOR[@type='Processor']">
    <H2>
      <A><xsl:attribute name="name">#SECTION_<xsl:value-of select="@index"/></xsl:attribute></A>
      Section <xsl:value-of select="@name"/>
    </H2>
    Processor : <xsl:value-of select="PROCESSOR"/>
    <P/><HR size="4" noshade="1"/>
  </xsl:template>

  <xsl:template match="SECTION_SEGMENT_INFO[@type='Segment info']">
    <H2>
      <A><xsl:attribute name="name">#SECTION_<xsl:value-of select="@index"/></xsl:attribute></A>
      Section <xsl:value-of select="@name"/>
    </H2>
    <TABLE border="1" width="100%" cellpadding="0" cellspacing="0">
    <THEAD bgcolor="#006fff">
      <TR>
        <TH>Name</TH>
        <TH>Beggining Address</TH>
        <TH>Ending Address</TH>
        <TH>Memory Type</TH>
        <TH>Memory Width</TH>
        <TH>Memory Access</TH>
      </TR>
    </THEAD>
    <TBODY bgolor="#88ccff">
      <xsl:for-each select="SEGMENT">
      <TR>
        <TD><xsl:value-of select="@name"/></TD>
        <TD align="right"><xsl:value-of select="@begin_address"/></TD>
        <TD align="right"><xsl:value-of select="@end_address"/></TD>
        <TD align="right"><xsl:value-of select="@memory_type"/></TD>
        <TD align="right"><xsl:value-of select="@memory_width"/></TD>
        <TD align="right"><xsl:value-of select="@memory_access"/></TD>
      </TR>
      </xsl:for-each>
    </TBODY>
    </TABLE>
    <P/><HR size="4" noshade="1"/>
  </xsl:template>

  <xsl:template match="SECTION_SYMBOL_TABLE[@type='Symbol Table']">
    <H2>
      <A><xsl:attribute name="name">#SECTION_<xsl:value-of select="@index"/></xsl:attribute></A>
      Section <xsl:value-of select="@name"/>
    </H2>
    <TABLE border="1" width="100%" cellpadding="0" cellspacing="0">
    <THEAD bgcolor="#006fff">
      <TR>
        <TH>Index</TH>
        <TH class="sortable">Name</TH>
        <TH>Section index</TH>
        <TH>Value</TH>
        <TH>Size</TH>
        <TH>Type</TH>
        <TH>Bind</TH>
        <TH>Flags</TH>
      </TR>
    </THEAD>
    <TBODY bgolor="#88ccff">
      <xsl:for-each select="SYMBOL">
      <TR>
        <TD>              <xsl:value-of select="@index"/></TD>
        <TD>              <xsl:value-of select="NAME"/></TD>
        <TD align="right"><xsl:value-of select="@shindex"/></TD>
        <TD align="right"><xsl:value-of select="@value"/></TD>
        <TD align="right"><xsl:value-of select="@size"/></TD>
        <TD>              <xsl:value-of select="@type"/></TD>
        <TD>              <xsl:value-of select="@bind"/></TD>
        <TD>              <xsl:value-of select="@flags"/></TD>
      </TR>
      </xsl:for-each>
    </TBODY>
    </TABLE>
    <P/><HR size="4" noshade="1"/>
  </xsl:template>

  <xsl:template match="SECTION_STRING_TABLE[(@type='String Table') or (@type='String Table Opt')]">
    <H2>
      <A><xsl:attribute name="name">#SECTION_<xsl:value-of select="@index"/></xsl:attribute></A>
      Section <xsl:value-of select="@name"/>
    </H2>
    <TABLE border="1" cellpadding="3" cellspacing="0">
    <THEAD bgcolor="#006fff">
      <TR>
        <TH>Offset</TH>
        <TH>Name</TH>
      </TR>
    </THEAD>
    <TBODY bgolor="#88ccff">
      <xsl:for-each select="STRING">
      <TR>
        <TD align = "right"><xsl:value-of select="@offset"/></TD>
        <TD>                <PRE/><xsl:value-of select="NAME"/></TD>
      </TR>
      </xsl:for-each>
    </TBODY>
    </TABLE>
    <P/><HR size="4" noshade="1"/>
  </xsl:template>

</xsl:stylesheet>
